"""Idempotent development seed. Never runs automatically in production."""
import os
from datetime import date
from sqlalchemy import select, text
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.entities import Department, Holiday, HolidayCalendar, Ledger, LeavePolicy, LeaveType, MobilePolicy, OrganizationSettings, RoleAssignment, Team, User, WorkSchedule


def seed(db):
    if db.scalar(select(User.id).limit(1)):
        return
    db.add_all([Department(id=1, name='Product & Engineering', description='Building thoughtful products'), Department(id=2, name='People & Operations'), HolidayCalendar(id=1, name='Bulgaria · company calendar'), OrganizationSettings(id=1, name='Workleave')])
    db.flush()
    db.add_all([Team(id=1, name='Product Studio', department_id=1), Team(id=2, name='People Team', department_id=2), WorkSchedule(id=1, name='Standard · Monday–Friday', weekdays=[0, 1, 2, 3, 4], holiday_calendar_id=1), LeaveType(id=1, name='Annual paid leave'), LeaveType(id=2, name='Unpaid leave', paid=False, tracks_balance=False), LeavePolicy(id=1, name='Standard annual leave', annual_allowance=25), MobilePolicy(id=1, name='Flexible working', monthly_limit=8, weekly_limit=3)])
    db.flush()
    people = [('manager', 'Alex', 'Morgan', 1, 1, ['EMPLOYEE', 'MANAGER']), ('employee', 'Jamie', 'Parker', 1, 1, ['EMPLOYEE']), ('hr', 'Sam', 'Rivera', 2, 2, ['EMPLOYEE', 'HR']), ('admin', 'Taylor', 'Chen', 2, 2, ['EMPLOYEE', 'ADMIN']), ('colleague', 'Robin', 'Lee', 1, 1, ['EMPLOYEE'])]
    for i, (username, first, last, team, department, roles) in enumerate(people, 1):
        db.add(User(id=i, identity_provider_subject=os.environ.get(f'CLERK_SEED_{username.upper()}_ID') or f'unlinked:{username}', email=f'{username}@workleave.test', first_name=first, last_name=last, employee_number=f'WL-{i:03d}', manager_id=None if i == 1 else 1, team_id=team, department_id=department, schedule_id=1, leave_policy_id=1, mobile_policy_id=1, employment_start_date=date(2020, 1, 1)))
        db.flush()
        for role in roles:
            db.add(RoleAssignment(user_id=i, role=role))
        for year in range(date.today().year, date.today().year+2):
            db.add(Ledger(employee_id=i, leave_type_id=1, year=year, effective_date=date(year, 1, 1), amount=25, transaction_type='ACCRUAL', reason='Development seed annual entitlement', created_by=1, idempotency_key=f'entitlement:{i}:1:{year}:1'))
    # Illustrative fixed-date seed, deliberately not a legal holiday calculator.
    fixed = [(1, 1, 'New Year'), (3, 3, 'Liberation Day'), (5, 1, 'Labour Day'), (5, 6, 'St George’s Day'), (5, 24, 'Culture and Literacy Day'), (9, 6, 'Unification Day'), (9, 22, 'Independence Day'), (12, 24, 'Christmas Eve'), (12, 25, 'Christmas Day'), (12, 26, 'Christmas holiday')]
    for year in range(date.today().year, date.today().year+2):
        for month, day, name in fixed:
            db.add(Holiday(calendar_id=1, date=date(year, month, day), name=name))
    db.flush()
    if db.bind.dialect.name == 'postgresql':
        # Explicit development IDs must advance their identity sequences.
        for table in (Department, Team, HolidayCalendar, WorkSchedule, LeaveType, LeavePolicy, MobilePolicy, User, OrganizationSettings):
            name = table.__tablename__
            db.execute(text(f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), (SELECT max(id) FROM {name}))"))


if __name__ == '__main__':
    if settings().environment == 'production':
        raise SystemExit('Development seed is disabled in production')
    with SessionLocal.begin() as db:
        seed(db)
    print('Development organization seeded.')
