"""Explicit first administrator provisioning for an empty production database."""
import argparse
from datetime import date
from sqlalchemy import select
from app.core.db import SessionLocal
from app.models.entities import Department, HolidayCalendar, LeavePolicy, LeaveType, MobilePolicy, OrganizationSettings, RoleAssignment, Team, User, WorkSchedule
from app.services.common import audit


def bootstrap(subject, email, first_name, last_name, organization):
    if not subject.startswith('user_'):
        raise SystemExit('Supply the Clerk user_… identifier for --subject.')
    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).limit(1)):
            raise SystemExit('Organization already initialized; use authorized employee administration.')
        department=Department(name='People & Operations');calendar=HolidayCalendar(name='Company holidays');leave=LeavePolicy(name='Standard annual leave',annual_allowance=25);mobile=MobilePolicy(name='Standard mobile work')
        db.add_all([department,calendar,leave,mobile,OrganizationSettings(name=organization)]);db.flush()
        team=Team(name='People Team',department_id=department.id);schedule=WorkSchedule(name='Monday–Friday',holiday_calendar_id=calendar.id)
        db.add_all([team,schedule,LeaveType(name='Annual paid leave'),LeaveType(name='Unpaid leave',paid=False,tracks_balance=False)]);db.flush()
        admin=User(identity_provider_subject=subject,email=email,first_name=first_name,last_name=last_name,employee_number='INITIAL-ADMIN',team_id=team.id,department_id=department.id,schedule_id=schedule.id,leave_policy_id=leave.id,mobile_policy_id=mobile.id,employment_start_date=date.today())
        db.add(admin);db.flush()
        for role in ['EMPLOYEE','ADMIN','HR']:
            db.add(RoleAssignment(user_id=admin.id,role=role))
        audit(db,admin,'ORGANIZATION_BOOTSTRAPPED','organization',1)
    print('Initial account provisioned. Review policies, calendars and roles before onboarding employees.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for field in ['subject','email','first-name','last-name','organization']:
        parser.add_argument('--'+field,required=True)
    args=parser.parse_args()
    bootstrap(args.subject,args.email,args.first_name,args.last_name,args.organization)
