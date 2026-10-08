from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import delete, select
from app.core.auth import has_role
from app.core.errors import require
from app.models.entities import Approval, Holiday, LeaveDetail, LeavePolicy, LeaveType, MobileDetail, MobilePolicy, Request, RequestDay, RoleAssignment, User, WorkSchedule
from app.policies.calculation import overlaps, working_days
from app.schemas.contracts import RequestInput
from app.services.balances import balance, debit_days, reverse_request
from app.services.common import audit, local_today, lock_employee, notify

ACTIVE = ('PENDING', 'APPROVED', 'CANCELLATION_REQUESTED')
TRANSITIONS = {
    'submit': {'DRAFT': 'PENDING'},
    'withdraw': {'DRAFT': 'CANCELLED', 'PENDING': 'CANCELLED'},
    'cancel': {'APPROVED': 'CANCELLATION_REQUESTED'},
    'approve': {'PENDING': 'APPROVED', 'CANCELLATION_REQUESTED': 'CANCELLED'},
    'reject': {'PENDING': 'REJECTED', 'CANCELLATION_REQUESTED': 'APPROVED'},
}


def input_for(db, request):
    data = {k: getattr(request, k) for k in ('kind', 'start_date', 'end_date', 'portion', 'comment')}
    if request.kind == 'LEAVE':
        data['leave_type_id'] = db.get(LeaveDetail, request.id).leave_type_id
    else:
        detail = db.get(MobileDetail, request.id)
        data.update({k: getattr(detail, k) for k in ('location_type', 'city', 'country')})
    return RequestInput(**data)


def calculate(db, employee, data):
    schedule = db.get(WorkSchedule, employee.schedule_id)
    holidays = set(db.scalars(select(Holiday.date).where(Holiday.calendar_id == schedule.holiday_calendar_id))) if not schedule.work_on_holidays else set()
    return working_days(data.start_date, data.end_date, schedule.weekdays, holidays, data.portion)


def validation(db, employee, data, request_id=None, approving=False, submitted_on=None):
    require(employee.status == 'ACTIVE', 'Employee is inactive')
    require(data.start_date >= employee.employment_start_date, 'Request begins before employment')
    require(not employee.employment_end_date or data.end_date <= employee.employment_end_date, 'Request ends after employment')
    if not approving:
        require(data.start_date >= local_today(employee), 'Requests cannot start in the past')
    days = calculate(db, employee, data)
    require(days, 'The selected dates contain no scheduled working days')
    existing = db.execute(select(RequestDay, Request).join(Request, Request.id == RequestDay.request_id).where(Request.employee_id == employee.id, Request.status.in_(ACTIVE), Request.id != (request_id or -1), RequestDay.date >= data.start_date, RequestDay.date <= data.end_date)).all()
    for day, _, portion in days:
        require(not any(rd.date == day and overlaps(rd.portion, portion) for rd, _ in existing), 'These dates overlap an existing request', 'date_conflict', 409)
    flags = []
    if data.kind == 'LEAVE':
        leave_type = db.get(LeaveType, data.leave_type_id)
        require(leave_type is not None, 'Leave type not found')
        require(data.portion == 'FULL' or leave_type.allow_half_day, 'This leave type does not allow half days')
        policy = db.get(LeavePolicy, employee.leave_policy_id)
        require(data.start_date >= policy.valid_from and (not policy.valid_until or data.end_date <= policy.valid_until), 'Leave policy is not valid for the requested dates')
    else:
        policy = db.get(MobilePolicy, employee.mobile_policy_id)
        if data.start_date < (submitted_on or local_today(employee)) + timedelta(days=policy.advance_notice_days):
            flags.append('advance_notice')
        if any(day.weekday() not in policy.allowed_weekdays for day, _, _ in days):
            flags.append('restricted_weekday')
        if data.location_type not in policy.allowed_locations:
            flags.append('restricted_location')
        if data.country in policy.restricted_countries:
            flags.append('restricted_country')
        # Pending requests reserve quota; revalidate approvals under the employee lock.
        remote = db.execute(select(RequestDay).join(Request, Request.id == RequestDay.request_id).where(Request.employee_id == employee.id, Request.kind == 'MOBILE', Request.status.in_(ACTIVE), Request.id != (request_id or -1))).scalars().all()
        monthly, weekly = defaultdict(Decimal), defaultdict(Decimal)
        for day, amount in [(d.date, d.day_fraction) for d in remote] + [(d, a) for d, a, _ in days]:
            monthly[(day.year, day.month)] += amount
            weekly[day.isocalendar()[:2]] += amount
        if any(monthly[(d.year, d.month)] > policy.monthly_limit for d, _, _ in days):
            flags.append('monthly_quota')
        if any(weekly[d.isocalendar()[:2]] > policy.weekly_limit for d, _, _ in days):
            flags.append('weekly_quota')
        require(not flags or policy.allow_hr_override, 'Mobile-work policy violation: ' + ', '.join(flags), 'policy_violation', 409)
        if data.location_type == 'ABROAD' and policy.international_requires_hr:
            flags.append('international_review')
    return days, flags


def preview(db, employee, data):
    days, flags = validation(db, employee, data)
    by_year = defaultdict(Decimal)
    for day, amount, _ in days:
        by_year[day.year] += amount
    return {'days': sum((d[1] for d in days), Decimal(0)), 'dates': [dict(date=d, fraction=a, portion=p) for d, a, p in days], 'exceptions': flags, 'years': [{'year': year, 'days': amount, 'available': balance(db, employee.id, data.leave_type_id, year, min(d for d, _, _ in days if d.year == year)) if data.kind == 'LEAVE' else None} for year, amount in by_year.items()]}


def can_review(db, actor, request, employee):
    if actor.id == employee.id:
        return False
    if request.exception_flags:
        return has_role(db, actor, 'HR')
    policy = db.get(LeavePolicy if request.kind == 'LEAVE' else MobilePolicy, employee.leave_policy_id if request.kind == 'LEAVE' else employee.mobile_policy_id)
    if request.kind == 'MOBILE' and policy.international_requires_hr and db.get(MobileDetail, request.id).location_type == 'ABROAD':
        return has_role(db, actor, 'HR')
    return (employee.manager_id == actor.id and has_role(db, actor, 'MANAGER')) or (has_role(db, actor, 'HR') and policy.allow_hr_override)


def approvers(db, request, employee):
    if request.exception_flags:
        return list(db.scalars(select(User.id).join(RoleAssignment, RoleAssignment.user_id == User.id).where(RoleAssignment.role == 'HR', User.id != employee.id, User.status == 'ACTIVE')))
    if employee.manager_id and employee.manager_id != employee.id:
        manager = db.get(User, employee.manager_id)
        if manager and manager.status == 'ACTIVE' and has_role(db, manager, 'MANAGER'):
            return [manager.id]
    return []


def create(db, actor, data):
    employee = lock_employee(db, actor.id)
    days, flags = validation(db, employee, data)
    request = Request(employee_id=employee.id, kind=data.kind, start_date=data.start_date, end_date=data.end_date, portion=data.portion, comment=data.comment, exception_flags=flags, status='DRAFT')
    db.add(request)
    db.flush()
    if data.kind == 'LEAVE':
        db.add(LeaveDetail(request_id=request.id, leave_type_id=data.leave_type_id))
    else:
        db.add(MobileDetail(request_id=request.id, location_type=data.location_type, city=data.city, country=data.country))
    for day, amount, portion in days:
        db.add(RequestDay(request_id=request.id, date=day, day_fraction=amount, portion=portion))
    audit(db, actor, 'REQUEST_CREATED', 'request', request.id)
    db.flush()
    if data.submit:
        from app.schemas.contracts import Decision
        transition(db, actor, request.id, 'submit', Decision())
    return request


def apply_approval(db, actor, request, employee, data, days, override, system=False):
    if data.kind == 'LEAVE' and db.get(LeaveType, data.leave_type_id).tracks_balance:
        debit_days(db, employee, data.leave_type_id, request, days, actor, override)
    request.status = 'APPROVED'
    if system:
        db.add(Approval(request_id=request.id, approver_id=None, decision='SYSTEM_APPROVED', comment='Approval not required by policy'))
        audit(db, None, 'SYSTEM_APPROVED', 'request', request.id, old_status='PENDING', new_status='APPROVED')
    notify(db, employee.id, 'REQUEST_APPROVED', request.id)


def transition(db, actor, request_id, action, decision):
    request = db.get(Request, request_id)
    require(request, 'Request not found', 'not_found', 404)
    employee = lock_employee(db, request.employee_id)
    request = db.scalar(select(Request).where(Request.id == request_id).with_for_update().execution_options(populate_existing=True))
    old = request.status
    require(action in TRANSITIONS and old in TRANSITIONS[action], 'This action is not valid for the current request status', 'invalid_transition', 409)
    if action in ('submit', 'withdraw', 'cancel'):
        require(actor.id == employee.id, 'Only the request owner can do this', 'forbidden', 403)
    else:
        policy = db.get(LeavePolicy if request.kind == 'LEAVE' else MobilePolicy, employee.leave_policy_id if request.kind == 'LEAVE' else employee.mobile_policy_id)
        override = bool(decision.override_reason and has_role(db, actor, 'HR') and policy.allow_hr_override)
        require(actor.id != employee.id and (can_review(db, actor, request, employee) or override), 'You are not an authorized approver for this request', 'forbidden', 403)
        international = request.kind == 'MOBILE' and policy.international_requires_hr and db.get(MobileDetail, request.id).location_type == 'ABROAD'
        require(not decision.override_reason or override or (has_role(db, actor, 'HR') and international and not set(request.exception_flags).difference({'international_review'})), 'Policy does not permit this override', 'forbidden', 403)
        require(action != 'reject' or len(decision.comment) >= 3, 'A rejection reason is required')
        if action == 'approve' and employee.manager_id != actor.id:
            require(len(decision.override_reason) >= 3, 'HR approval requires a documented justification')
        if request.exception_flags and action == 'approve':
            require(len(decision.override_reason) >= 3, 'HR review requires a documented justification')
        db.add(Approval(request_id=request.id, approver_id=actor.id, decision=('CANCELLATION_' if old == 'CANCELLATION_REQUESTED' else '') + action.upper(), comment=decision.override_reason or decision.comment))
    request.status = TRANSITIONS[action][old]
    if action == 'submit':
        audit(db, actor, 'SUBMIT', 'request', request.id, old_status=old, new_status='PENDING')
        data = input_for(db, request)
        days, flags = validation(db, employee, data, request.id)
        request.exception_flags = flags
        db.execute(delete(RequestDay).where(RequestDay.request_id == request.id))
        for day, amount, portion in days:
            db.add(RequestDay(request_id=request.id, date=day, day_fraction=amount, portion=portion))
        approval_required = db.get(LeaveType, data.leave_type_id).approval_required if data.kind == 'LEAVE' else db.get(MobilePolicy, employee.mobile_policy_id).approval_required
        if approval_required or flags:
            recipients = approvers(db, request, employee)
            require(recipients, 'No eligible approver is assigned. Contact HR.', 'missing_approver', 409)
            for recipient in recipients:
                notify(db, recipient, 'MANAGER_APPROVAL_REQUIRED', request.id)
        else:
            apply_approval(db, actor, request, employee, data, days, False, system=True)
    elif action == 'approve' and old == 'PENDING':
        data = input_for(db, request)
        days, flags = validation(db, employee, data, request.id, approving=True, submitted_on=request.created_at.date())
        require(not flags or has_role(db, actor, 'HR'), 'Policy now requires HR review', 'forbidden', 403)
        require(not flags or len(decision.override_reason) >= 3, 'Exceptions require a documented HR justification')
        # Recalculate pending requests under current schedules; approved snapshots never change.
        db.execute(delete(RequestDay).where(RequestDay.request_id == request.id))
        for day, amount, portion in days:
            db.add(RequestDay(request_id=request.id, date=day, day_fraction=amount, portion=portion))
        apply_approval(db, actor, request, employee, data, days, override)
    elif action == 'approve' and old == 'CANCELLATION_REQUESTED':
        reverse_request(db, request, actor)
        notify(db, employee.id, 'CANCELLATION_APPROVED', request.id)
    elif action == 'reject':
        notify(db, employee.id, 'CANCELLATION_REJECTED' if old == 'CANCELLATION_REQUESTED' else 'REQUEST_REJECTED', request.id)
    elif action == 'cancel':
        recipients = approvers(db, request, employee)
        require(recipients, 'No eligible cancellation approver is assigned', 'missing_approver', 409)
        for recipient in recipients:
            notify(db, recipient, 'CANCELLATION_REQUESTED', request.id)
    elif action == 'withdraw':
        for recipient in approvers(db, request, employee):
            notify(db, recipient, 'REQUEST_WITHDRAWN', request.id)
    if action != 'submit':
        audit(db, actor, action.upper(), 'request', request.id, old_status=old, new_status=request.status, override_reason=decision.override_reason)
    db.flush()
    return request


def serialize(db, request, viewer):
    employee = db.get(User, request.employee_id)
    private = viewer.id == employee.id or (employee.manager_id == viewer.id and has_role(db, viewer, 'MANAGER'))
    days = list(db.scalars(select(RequestDay).where(RequestDay.request_id == request.id)))
    result = {k: getattr(request, k) for k in ('id', 'employee_id', 'kind', 'start_date', 'end_date', 'portion', 'status', 'created_at', 'exception_flags')}
    result.update(employee_name=f'{employee.first_name} {employee.last_name}', days=sum((d.day_fraction for d in days), Decimal(0)), can_approve=can_review(db, viewer, request, employee), requires_justification=bool(request.exception_flags) or employee.manager_id != viewer.id)
    if request.kind == 'LEAVE':
        detail = db.get(LeaveDetail, request.id)
        result['leave_type_id'] = detail.leave_type_id
        result['label'] = db.get(LeaveType, detail.leave_type_id).name
    else:
        detail = db.get(MobileDetail, request.id)
        result['label'] = 'Mobile work'
        result['location_type'] = detail.location_type
        if private or has_role(db, viewer, 'HR'):
            result.update(city=detail.city, country=detail.country)
    if private:
        result['comment'] = request.comment
        result['decisions'] = [{'decision': a.decision, 'comment': a.comment, 'decided_at': a.decided_at} for a in db.scalars(select(Approval).where(Approval.request_id == request.id).order_by(Approval.id))]
    return result
