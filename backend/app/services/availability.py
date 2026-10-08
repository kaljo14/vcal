from collections import defaultdict
from datetime import timedelta
from sqlalchemy import or_, select
from app.core.auth import has_role
from app.core.errors import require
from app.models.entities import Holiday, Request, RequestDay, User, WorkSchedule
from app.policies.calculation import working_days


def visible_people(db, actor):
    query = select(User).where(User.status == 'ACTIVE')
    if has_role(db, actor, 'HR'):
        return query
    if has_role(db, actor, 'MANAGER'):
        return query.where(or_(User.team_id == actor.team_id, User.manager_id == actor.id, User.id == actor.id))
    return query.where(User.team_id == actor.team_id)


def calendar_data(db, actor, start, end, team_id=None, department_id=None, employee_id=None):
    require(end >= start and (end-start).days <= 93, 'Calendar range must be between 1 and 94 days')
    query = visible_people(db, actor)
    for column, value in [(User.team_id, team_id), (User.department_id, department_id), (User.id, employee_id)]:
        if value is not None:
            query = query.where(column == value)
    people = list(db.scalars(query.order_by(User.first_name)))
    ids = [p.id for p in people]
    rows = db.execute(select(RequestDay, Request).join(Request, Request.id == RequestDay.request_id).where(Request.employee_id.in_(ids), Request.status.in_(['PENDING', 'APPROVED', 'CANCELLATION_REQUESTED']), RequestDay.date >= start, RequestDay.date <= end)).all() if ids else []
    events, stats = [], defaultdict(lambda: {'office': 0, 'remote': 0, 'leave': 0, 'pending': 0})
    holiday_events = {}
    for person in people:
        schedule = db.get(WorkSchedule, person.schedule_id)
        holidays = list(db.scalars(select(Holiday).where(Holiday.calendar_id == schedule.holiday_calendar_id, Holiday.date >= start, Holiday.date <= end)))
        for h in holidays:
            holiday_events[h.id] = {'id': f'holiday-{h.id}', 'title': h.name, 'start': h.date, 'end': h.date + timedelta(days=1), 'kind': 'HOLIDAY', 'status': 'APPROVED'}
        workdays = working_days(max(start, person.employment_start_date), min(end, person.employment_end_date or end), schedule.weekdays, set() if schedule.work_on_holidays else {h.date for h in holidays})
        # Existing approved day snapshots are also shown after schedule/holiday changes.
        dates = {d for d, _, _ in workdays} | {rd.date for rd, r in rows if r.employee_id == person.id}
        for day in sorted(dates):
            scheduled = any(d == day for d, _, _ in workdays)
            office = 1.0 if scheduled else 0.0
            for rd, request in rows:
                if request.employee_id != person.id or rd.date != day:
                    continue
                pending = request.status == 'PENDING'
                kind = 'MOBILE' if request.kind == 'MOBILE' else 'LEAVE'
                fraction = float(rd.day_fraction)
                if not pending:
                    office -= fraction
                    stats[str(day)]['remote' if kind == 'MOBILE' else 'leave'] += fraction
                else:
                    stats[str(day)]['pending'] += fraction
                events.append({'id': f'{request.id}-{day}', 'request_id': request.id if actor.id == person.id or person.manager_id == actor.id else None, 'employee_id': person.id, 'title': f'{person.first_name} {person.last_name} · {"Remote" if kind == "MOBILE" else "Away"}', 'start': day, 'end': day + timedelta(days=1), 'kind': kind, 'status': request.status, 'portion': rd.portion, 'fraction': fraction})
            if office > 0:
                stats[str(day)]['office'] += office
                events.append({'id': f'office-{person.id}-{day}', 'employee_id': person.id, 'title': f'{person.first_name} {person.last_name} · Office', 'start': day, 'end': day + timedelta(days=1), 'kind': 'OFFICE', 'status': 'APPROVED', 'fraction': office})
    return {'events': events + list(holiday_events.values()), 'statistics': dict(stats), 'employees': [{'id': p.id, 'name': f'{p.first_name} {p.last_name}', 'team_id': p.team_id} for p in people]}
