import csv
import io
from datetime import date
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.auth import authorize, current_user, has_role
from app.core.db import get_db
from app.core.errors import require
from app.models.entities import AuditLog, Department, Holiday, HolidayCalendar, Ledger, LeavePolicy, LeaveType, MobilePolicy, Notification, OrganizationSettings, Request, RequestDay, RoleAssignment, Team, User, WorkSchedule, utcnow
from app.schemas.contracts import Adjustment, Decision, DepartmentInput, EmployeeInput, Entitlement, HolidayInput, LeaveTypeInput, LeavePolicyInput, MobilePolicyInput, PolicyInput, PolicyPatch, Preferences, RequestInput, ScheduleInput, SettingsInput, TeamInput
from app.services import availability, balances, management, requests
from app.services.common import audit, local_today, lock_all_employees

router = APIRouter(prefix='/api/v1')
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(current_user)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


def raw(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


@router.get('/me')
def me(db: DB, actor: Actor):
    result = management.employee_data(db, actor)
    result['team'] = db.get(Team, actor.team_id).name
    result['department'] = db.get(Department, actor.department_id).name
    return result


@router.patch('/me/preferences')
def preferences(data: Preferences, db: DB, actor: Actor):
    actor.email_notifications = data.email_notifications
    return {'email_notifications': actor.email_notifications}


@router.get('/me/balances')
def my_balances(db: DB, actor: Actor, year: int | None = None):
    return balances.summary(db, actor, year or local_today(actor).year)


@router.get('/me/ledger')
def my_ledger(db: DB, actor: Actor, limit: Limit = 50, offset: Offset = 0):
    return [raw(e) for e in db.scalars(select(Ledger).where(Ledger.employee_id == actor.id).order_by(Ledger.id.desc()).offset(offset).limit(limit))]


@router.get('/me/dashboard')
def dashboard(db: DB, actor: Actor):
    today = local_today(actor)
    policy = db.get(MobilePolicy, actor.mobile_policy_id)
    used = db.scalar(select(func.coalesce(func.sum(RequestDay.day_fraction), 0)).join(Request, Request.id == RequestDay.request_id).where(Request.employee_id == actor.id, Request.kind == 'MOBILE', Request.status.in_(['APPROVED', 'CANCELLATION_REQUESTED']), func.extract('year', RequestDay.date) == today.year, func.extract('month', RequestDay.date) == today.month))
    pending_mobile = db.scalar(select(func.coalesce(func.sum(RequestDay.day_fraction), 0)).join(Request, Request.id == RequestDay.request_id).where(Request.employee_id == actor.id, Request.kind == 'MOBILE', Request.status == 'PENDING', func.extract('year', RequestDay.date) == today.year, func.extract('month', RequestDay.date) == today.month))
    recent = list(db.scalars(select(Request).where(Request.employee_id == actor.id).order_by(Request.id.desc()).limit(8)))
    upcoming = list(db.scalars(select(Request).where(Request.employee_id == actor.id, Request.status == 'APPROVED', Request.end_date >= today).order_by(Request.start_date).limit(10)))
    return {'balances': balances.summary(db, actor, today.year), 'mobile': {'used': used, 'remaining': max(0, policy.monthly_limit-used-pending_mobile), 'pending': pending_mobile, 'limit': policy.monthly_limit}, 'recent': [requests.serialize(db, r, actor) for r in recent], 'upcoming': [requests.serialize(db, r, actor) for r in upcoming], 'pending_count': db.scalar(select(func.count()).select_from(Request).where(Request.employee_id == actor.id, Request.status == 'PENDING')), 'today': availability.calendar_data(db, actor, today, today)}


@router.post('/requests/preview')
def preview_request(data: RequestInput, db: DB, actor: Actor):
    return requests.preview(db, actor, data)


@router.post('/requests', status_code=201)
def create_request(data: RequestInput, db: DB, actor: Actor):
    return requests.serialize(db, requests.create(db, actor, data), actor)


@router.get('/requests')
def list_requests(db: DB, actor: Actor, scope: Literal['mine', 'approvals'] = 'mine', status: str | None = None, limit: Limit = 50, offset: Offset = 0):
    query = select(Request)
    if scope == 'mine':
        query = query.where(Request.employee_id == actor.id)
    else:
        authorize(db, actor, 'MANAGER', 'HR')
        if not has_role(db, actor, 'HR'):
            query = query.join(User, User.id == Request.employee_id).where(User.manager_id == actor.id, User.id != actor.id)
    if status:
        query = query.where(Request.status == status)
    candidates = list(db.scalars(query.order_by(Request.created_at.desc())))
    if scope == 'approvals':
        candidates = [r for r in candidates if requests.can_review(db, actor, r, db.get(User, r.employee_id))]
    return {'items': [requests.serialize(db, r, actor) for r in candidates[offset:offset+limit]], 'total': len(candidates)}


@router.get('/requests/{request_id}')
def get_request(request_id: int, db: DB, actor: Actor):
    request = db.get(Request, request_id)
    require(request, 'Request not found', 'not_found', 404)
    employee = db.get(User, request.employee_id)
    require(actor.id == employee.id or requests.can_review(db, actor, request, employee) or has_role(db, actor, 'HR'), 'Request not found', 'not_found', 404)
    return requests.serialize(db, request, actor)


@router.post('/requests/{request_id}/{action}')
def transition_request(request_id: int, action: Literal['submit', 'withdraw', 'cancel', 'approve', 'reject'], data: Decision, db: DB, actor: Actor):
    return requests.serialize(db, requests.transition(db, actor, request_id, action, data), actor)


@router.get('/calendar')
def calendar(db: DB, actor: Actor, start: date, end: date, team_id: int | None = None, department_id: int | None = None, employee_id: int | None = None):
    return availability.calendar_data(db, actor, start, end, team_id, department_id, employee_id)


@router.get('/calendar/team/{team_id}')
def team_calendar(team_id: int, db: DB, actor: Actor, start: date, end: date):
    return availability.calendar_data(db, actor, start, end, team_id)


@router.get('/employees')
def employees(db: DB, actor: Actor, limit: Limit = 50, offset: Offset = 0, search: str = '', status: Literal['ACTIVE', 'INACTIVE'] | None = None):
    full = has_role(db, actor, 'HR', 'ADMIN')
    query = select(User) if full else availability.visible_people(db, actor)
    if status:
        query = query.where(User.status == status)
    if search:
        query = query.where((User.first_name + ' ' + User.last_name).ilike('%' + search[:100] + '%'))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {'items': [management.employee_data(db, u, full) for u in db.scalars(query.order_by(User.first_name).offset(offset).limit(limit))], 'total': total}


@router.get('/managers')
def managers(db: DB, actor: Actor):
    people = db.scalars(select(User).join(RoleAssignment, RoleAssignment.user_id == User.id).where(RoleAssignment.role == 'MANAGER', User.status == 'ACTIVE').order_by(User.first_name, User.last_name, User.id))
    return [{'id': person.id, 'first_name': person.first_name, 'last_name': person.last_name, 'employee_number': person.employee_number} for person in people]


@router.post('/employees', status_code=201)
def create_employee(data: EmployeeInput, db: DB, actor: Actor):
    authorize(db, actor, 'HR', 'ADMIN')
    return management.employee_data(db, management.save_employee(db, actor, data))


@router.patch('/employees/{employee_id}')
def edit_employee(employee_id: int, data: dict, db: DB, actor: Actor):
    authorize(db, actor, 'HR', 'ADMIN')
    return management.employee_data(db, management.patch_employee(db, actor, employee_id, data))


@router.get('/employees/{employee_id}/ledger')
def employee_ledger(employee_id: int, db: DB, actor: Actor, limit: Limit = 50, offset: Offset = 0):
    require(actor.id == employee_id or has_role(db, actor, 'HR'), 'Permission denied', 'forbidden', 403)
    return [raw(e) for e in db.scalars(select(Ledger).where(Ledger.employee_id == employee_id).order_by(Ledger.id.desc()).offset(offset).limit(limit))]


@router.post('/employees/{employee_id}/adjustments')
def adjust(employee_id: int, data: Adjustment, db: DB, actor: Actor):
    authorize(db, actor, 'HR')
    return raw(balances.adjustment(db, actor, employee_id, data))


@router.post('/employees/{employee_id}/entitlements')
def grant(employee_id: int, data: Entitlement, db: DB, actor: Actor):
    authorize(db, actor, 'HR')
    return raw(balances.entitlement(db, actor, employee_id, data))


@router.post('/employees/{employee_id}/carryover')
def carryover(employee_id: int, data: Entitlement, db: DB, actor: Actor):
    authorize(db, actor, 'HR')
    return raw(balances.entitlement(db, actor, employee_id, data, True))


@router.get('/policies')
def policies(db: DB, actor: Actor):
    # All employees can read the rules that apply to their requests.
    return {'leave': [raw(p) for p in db.scalars(select(LeavePolicy))], 'mobile': [raw(p) for p in db.scalars(select(MobilePolicy))]}


@router.post('/policies', status_code=201)
def create_policy(data: PolicyInput, db: DB, actor: Actor):
    authorize(db, actor, 'HR', 'ADMIN')
    model = LeavePolicy if data.kind == 'leave' else MobilePolicy
    policy = model(**data.config)
    db.add(policy)
    db.flush()
    audit(db, actor, 'POLICY_CREATED', data.kind + '_policy', policy.id)
    return raw(policy)


@router.patch('/policies/{policy_id}')
def update_policy(policy_id: int, data: PolicyPatch, db: DB, actor: Actor):
    authorize(db, actor, 'HR', 'ADMIN')
    lock_all_employees(db)
    policy = db.get(LeavePolicy if data.kind == 'leave' else MobilePolicy, policy_id)
    require(policy, 'Policy not found', 'not_found', 404)
    existing = raw(policy)
    existing.pop('id')
    schema = LeavePolicyInput if data.kind == 'leave' else MobilePolicyInput
    validated = schema.model_validate({**existing, **data.config})
    for key, value in validated.model_dump().items():
        setattr(policy, key, value)
    audit(db, actor, 'POLICY_UPDATED', data.kind + '_policy', policy.id, changed_fields=list(data.config))
    return raw(policy)


@router.get('/departments')
def departments(db: DB, actor: Actor):
    return [raw(r) for r in db.scalars(select(Department).order_by(Department.name))]


@router.post('/departments', status_code=201)
def add_department(data: DepartmentInput, db: DB, actor: Actor):
    authorize(db, actor, 'ADMIN')
    row = Department(**data.model_dump())
    db.add(row)
    db.flush()
    audit(db, actor, 'DEPARTMENT_CREATED', 'department', row.id)
    return raw(row)


@router.delete('/departments/{department_id}', status_code=204)
def delete_department(department_id: int, db: DB, actor: Actor):
    authorize(db, actor, 'ADMIN')
    department = db.scalar(select(Department).where(Department.id == department_id).with_for_update())
    require(department, 'Department not found', 'not_found', 404)
    team_ids = list(db.scalars(select(Team.id).where(Team.department_id == department_id)))
    employee_count = db.scalar(select(func.count()).select_from(User).where((User.department_id == department_id) | (User.team_id.in_(team_ids))))
    require(not employee_count, 'Move employees out of this department and its teams before deleting it.', 'department_in_use', 409)
    for team in db.scalars(select(Team).where(Team.department_id == department_id)):
        db.delete(team)
    db.flush()
    db.delete(department)
    audit(db, actor, 'DEPARTMENT_DELETED', 'department', department_id)
    return Response(status_code=204)


@router.get('/teams')
def teams(db: DB, actor: Actor):
    return [raw(r) for r in db.scalars(select(Team).order_by(Team.name))]


@router.post('/teams', status_code=201)
def add_team(data: TeamInput, db: DB, actor: Actor):
    authorize(db, actor, 'ADMIN')
    require(db.get(Department, data.department_id), 'Department not found')
    row = Team(**data.model_dump())
    db.add(row)
    db.flush()
    audit(db, actor, 'TEAM_CREATED', 'team', row.id)
    return raw(row)


@router.get('/schedules')
def schedules(db: DB, actor: Actor):
    return [raw(r) for r in db.scalars(select(WorkSchedule))]


@router.post('/schedules', status_code=201)
def add_schedule(data: ScheduleInput, db: DB, actor: Actor):
    authorize(db, actor, 'HR')
    require(db.get(HolidayCalendar, data.holiday_calendar_id), 'Holiday calendar not found')
    row = WorkSchedule(**data.model_dump())
    db.add(row)
    db.flush()
    audit(db, actor, 'SCHEDULE_CREATED', 'schedule', row.id)
    return raw(row)


@router.get('/holiday-calendars')
def holiday_calendars(db: DB, actor: Actor):
    return [raw(r) for r in db.scalars(select(HolidayCalendar))]


@router.post('/holiday-calendars', status_code=201)
def add_holiday_calendar(data: DepartmentInput, db: DB, actor: Actor):
    authorize(db, actor, 'HR')
    row = HolidayCalendar(name=data.name)
    db.add(row)
    db.flush()
    audit(db, actor, 'HOLIDAY_CALENDAR_CREATED', 'holiday_calendar', row.id)
    return raw(row)


@router.get('/holidays')
def holidays(db: DB, actor: Actor, year: int | None = None):
    query = select(Holiday)
    if year:
        query = query.where(func.extract('year', Holiday.date) == year)
    return [raw(r) for r in db.scalars(query.order_by(Holiday.date))]


@router.post('/holidays', status_code=201)
def add_holiday(data: HolidayInput, db: DB, actor: Actor):
    authorize(db, actor, 'HR')
    lock_all_employees(db)
    require(db.get(HolidayCalendar, data.calendar_id), 'Holiday calendar not found')
    row = Holiday(**data.model_dump())
    db.add(row)
    db.flush()
    audit(db, actor, 'HOLIDAY_CREATED', 'holiday', row.id)
    return raw(row)


@router.delete('/holidays/{holiday_id}', status_code=204)
def delete_holiday(holiday_id: int, db: DB, actor: Actor):
    authorize(db, actor, 'HR')
    lock_all_employees(db)
    row = db.get(Holiday, holiday_id)
    require(row, 'Holiday not found', 'not_found', 404)
    db.delete(row)
    audit(db, actor, 'HOLIDAY_DELETED', 'holiday', holiday_id)


@router.get('/leave-types')
def leave_types(db: DB, actor: Actor):
    return [raw(r) for r in db.scalars(select(LeaveType))]


@router.post('/leave-types', status_code=201)
def add_leave_type(data: LeaveTypeInput, db: DB, actor: Actor):
    authorize(db, actor, 'HR')
    row = LeaveType(**data.model_dump())
    db.add(row)
    db.flush()
    audit(db, actor, 'LEAVE_TYPE_CREATED', 'leave_type', row.id)
    return raw(row)


@router.get('/notifications')
def notifications(db: DB, actor: Actor, limit: Limit = 50, offset: Offset = 0):
    return [raw(n) for n in db.scalars(select(Notification).where(Notification.user_id == actor.id).order_by(Notification.id.desc()).offset(offset).limit(limit))]


@router.post('/notifications/{notification_id}/read')
def read_notification(notification_id: int, db: DB, actor: Actor):
    row = db.get(Notification, notification_id)
    require(row and row.user_id == actor.id, 'Notification not found', 'not_found', 404)
    row.read_at = utcnow()
    return raw(row)


@router.get('/audit')
def audit_log(db: DB, actor: Actor, limit: Limit = 50, offset: Offset = 0):
    authorize(db, actor, 'ADMIN')
    # Operational audit excludes free-text justifications; HR ledger retains them.
    return [{**raw(a), 'details': {k: v for k, v in a.details.items() if k not in ('reason', 'override_reason')}} for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit))]


@router.get('/settings')
def get_settings(db: DB, actor: Actor):
    return raw(db.get(OrganizationSettings, 1))


@router.patch('/settings')
def settings(data: SettingsInput, db: DB, actor: Actor):
    authorize(db, actor, 'ADMIN')
    row = db.get(OrganizationSettings, 1)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    audit(db, actor, 'SETTINGS_UPDATED', 'settings', 1)
    return raw(row)


def report_response(rows, format):
    if format != 'csv':
        return rows
    buffer = io.StringIO()
    fields = list(rows[0]) if rows else ['employee_id', 'name', 'days']
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: "'"+v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for k, v in row.items()})
    return Response(buffer.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="workleave-report.csv"'})


@router.get('/reports/{report}')
def reports(report: Literal['leave', 'mobile-work', 'team-availability', 'balances', 'pending'], db: DB, actor: Actor, start: date, end: date, format: Literal['json', 'csv'] = 'json'):
    authorize(db, actor, 'HR', 'MANAGER')
    require(end >= start and (end-start).days <= 366, 'Report range must not exceed 367 days')
    if report in ('balances', 'leave'):
        authorize(db, actor, 'HR')
    people = list(db.scalars(select(User).where(User.status == 'ACTIVE'))) if has_role(db, actor, 'HR') else list(db.scalars(select(User).where(User.manager_id == actor.id, User.status == 'ACTIVE')))
    rows = []
    if report == 'team-availability':
        require((end-start).days <= 93, 'Availability reports support up to 94 days')
        data = availability.calendar_data(db, actor, start, end)
        rows = [{'date': day, **counts} for day, counts in data['statistics'].items()]
    else:
        for person in people:
            base = {'employee_id': person.id, 'name': f'{person.first_name} {person.last_name}'}
            if report == 'balances':
                rows.extend({**base, **b} for b in balances.summary(db, person, end.year))
            else:
                query = select(func.coalesce(func.sum(RequestDay.day_fraction), 0)).join(Request, Request.id == RequestDay.request_id).where(Request.employee_id == person.id, RequestDay.date >= start, RequestDay.date <= end)
                query = query.where(Request.status == 'PENDING') if report == 'pending' else query.where(Request.status.in_(['APPROVED', 'CANCELLATION_REQUESTED']), Request.kind == ('LEAVE' if report == 'leave' else 'MOBILE'))
                rows.append({**base, 'days': db.scalar(query)})
    return report_response(rows, format)
