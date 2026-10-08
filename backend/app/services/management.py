from sqlalchemy import delete, select
from app.core.auth import has_role, roles
from app.core.errors import require
from app.models.entities import Department, LeavePolicy, MobilePolicy, RoleAssignment, Team, User, WorkSchedule
from app.schemas.contracts import EmployeeInput
from app.services.common import audit, lock_all_employees


def employee_data(db, employee, full=True):
    fields = ['id', 'first_name', 'last_name', 'team_id', 'department_id', 'manager_id', 'status']
    if full:
        fields += ['identity_provider_subject', 'email', 'employee_number', 'schedule_id', 'leave_policy_id', 'mobile_policy_id', 'employment_start_date', 'employment_end_date', 'timezone', 'email_notifications']
    data = {field: getattr(employee, field) for field in fields}
    if full:
        data['roles'] = sorted(roles(db, employee))
    return data


def save_employee(db, actor, data, employee_id=None):
    lock_all_employees(db)
    previous = db.get(User, employee_id) if employee_id else None
    if employee_id:
        require(previous, 'Employee not found', 'not_found', 404)
    current_roles = roles(db, previous) if previous else {'EMPLOYEE'}
    require(set(data.roles) == current_roles or has_role(db, actor, 'ADMIN'), 'Only administrators can assign roles', 'forbidden', 403)
    if previous and data.identity_provider_subject != previous.identity_provider_subject:
        require(has_role(db, actor, 'ADMIN'), 'Only administrators can change linked identities', 'forbidden', 403)
    for model, value in [(Department, data.department_id), (Team, data.team_id), (WorkSchedule, data.schedule_id), (LeavePolicy, data.leave_policy_id), (MobilePolicy, data.mobile_policy_id)]:
        require(db.get(model, value), f'{model.__name__} not found')
    require(db.get(Team, data.team_id).department_id == data.department_id, 'Team must belong to selected department')
    require(not data.employment_end_date or data.employment_end_date >= data.employment_start_date, 'Employment end must follow start')
    seen = {employee_id} if employee_id else set()
    manager_id = data.manager_id
    while manager_id:
        require(manager_id not in seen, 'Reporting hierarchy contains a cycle')
        seen.add(manager_id)
        manager = db.get(User, manager_id)
        require(manager and manager.status == 'ACTIVE' and has_role(db, manager, 'MANAGER'), 'Manager must be an active employee with the manager role')
        manager_id = manager.manager_id
    if previous and previous.status == 'ACTIVE' and data.status == 'INACTIVE':
        active_report = db.scalar(select(User.id).where(User.manager_id == previous.id, User.status == 'ACTIVE').limit(1))
        require(active_report is None, 'Reassign active direct reports before removing this employee')
    if previous and previous.id == actor.id:
        require(data.status == 'ACTIVE' and ('ADMIN' not in current_roles or 'ADMIN' in data.roles), 'You cannot disable your own administrative access')
    employee = previous or User()
    for key, value in data.model_dump(exclude={'roles'}).items():
        setattr(employee, key, value)
    db.add(employee)
    db.flush()
    db.execute(delete(RoleAssignment).where(RoleAssignment.user_id == employee.id))
    for role in set(data.roles) | {'EMPLOYEE'}:
        db.add(RoleAssignment(user_id=employee.id, role=role))
    audit(db, actor, 'EMPLOYEE_UPDATED' if previous else 'EMPLOYEE_CREATED', 'employee', employee.id, changed_fields=list(data.model_fields_set))
    db.flush()
    return employee


def patch_employee(db, actor, employee_id, changes):
    employee = db.get(User, employee_id)
    require(employee, 'Employee not found', 'not_found', 404)
    data = employee_data(db, employee)
    data.pop('id')
    data.pop('email_notifications')
    data.update(changes)
    return save_employee(db, actor, EmployeeInput.model_validate(data), employee_id)
