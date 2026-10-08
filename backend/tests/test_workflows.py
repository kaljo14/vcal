from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.models.entities import Department, Holiday, Ledger, LeavePolicy, MobilePolicy, Request, Team, User, WorkSchedule, RoleAssignment
from app.policies.calculation import working_days
from app.services import balances, requests
from app.schemas.contracts import Decision, RequestInput, Entitlement
from conftest import sign_in

def next_monday():
    today = date.today() + timedelta(days=14)
    return today + timedelta(days=(7-today.weekday()) % 7)

def payload(kind='LEAVE', start=None, end=None, **extra):
    start = start or next_monday()
    return dict(kind=kind, start_date=str(start), end_date=str(end or start), leave_type_id=1, **extra)

def test_schedule_weekend_holiday_halfday_and_crossyear():
    assert len(working_days(date(2026,12,28),date(2027,1,4),[0,1,2,3,4],{date(2027,1,1)}))==5
    assert sum(x[1] for x in working_days(date(2026,10,10),date(2026,10,10),[5],set(),'AM'))==Decimal('.5')
    assert not working_days(date(2026,10,10),date(2026,10,11),[0,1,2,3,4],set())

def test_complete_vacation_approval_and_cancellation(client,db):
    before=client.get('/api/v1/me/balances').json()[0]['available']
    response=client.post('/api/v1/requests',json=payload(comment='Private family plans'))
    assert response.status_code==201,response.text
    request=response.json(); rid=request['id']
    assert request['status']=='PENDING'
    assert Decimal(client.get('/api/v1/me/balances').json()[0]['pending'])==1
    assert client.get('/api/v1/me/balances').json()[0]['available']==before
    sign_in(db,1)
    response=client.post(f'/api/v1/requests/{rid}/approve',json={})
    assert response.status_code==200,response.text
    sign_in(db,2)
    assert Decimal(client.get('/api/v1/me/balances').json()[0]['available'])==Decimal(before)-1
    assert client.post(f'/api/v1/requests/{rid}/cancel',json={}).json()['status']=='CANCELLATION_REQUESTED'
    sign_in(db,1)
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).json()['status']=='CANCELLED'
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).status_code==409
    sign_in(db,2)
    assert client.get('/api/v1/me/balances').json()[0]['available']==before
    assert sum(e.amount for e in db.scalars(select(Ledger).where(Ledger.related_request_id==rid)))==0

def test_rejection_does_not_debit_and_requires_reason(client,db):
    rid=client.post('/api/v1/requests',json=payload('MOBILE')).json()['id'];sign_in(db,1)
    assert client.post(f'/api/v1/requests/{rid}/reject',json={}).status_code==422
    assert client.post(f'/api/v1/requests/{rid}/reject',json={'comment':'On-site workshop'}).json()['status']=='REJECTED'
    sign_in(db,2)
    assert client.get(f'/api/v1/requests/{rid}').json()['decisions'][0]['comment']=='On-site workshop'
    assert not list(db.scalars(select(Ledger).where(Ledger.related_request_id==rid)))

def test_conflicts_duplicates_and_complementary_half_days(client):
    assert client.post('/api/v1/requests',json=payload(portion='AM')).status_code==201
    assert client.post('/api/v1/requests',json=payload('MOBILE',portion='AM')).status_code==409
    assert client.post('/api/v1/requests',json=payload('MOBILE',portion='PM')).status_code==201
    assert client.post('/api/v1/requests',json=payload()).status_code==409

def test_insufficient_funds(client,db):
    for e in db.scalars(select(Ledger).where(Ledger.employee_id==2)): e.amount=0
    db.commit();rid=client.post('/api/v1/requests',json=payload()).json()['id'];sign_in(db,1)
    response=client.post(f'/api/v1/requests/{rid}/approve',json={})
    assert response.status_code==409,response.text
    assert db.get(Request,rid).status=='PENDING'
    assert not list(db.scalars(select(Ledger).where(Ledger.related_request_id==rid)))

def test_object_permissions_and_calendar_privacy(client,db):
    rid=client.post('/api/v1/requests',json=payload(comment='Secret')).json()['id'];sign_in(db,5)
    assert client.get(f'/api/v1/requests/{rid}').status_code==404
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).status_code==403
    assert client.post(f'/api/v1/requests/{rid}/withdraw',json={}).status_code==403
    assert client.get('/api/v1/employees/2/ledger').status_code==403
    assert client.get('/api/v1/reports/leave',params={'start':str(next_monday()),'end':str(next_monday())}).status_code==403
    data=client.get('/api/v1/calendar',params={'start':str(next_monday()),'end':str(next_monday())}).json()
    assert 'Secret' not in str(data)
    sign_in(db,3)
    assert 'comment' not in client.get(f'/api/v1/requests/{rid}').json()

def test_no_self_approval(client,db):
    sign_in(db,1);db.get(User,1).manager_id=3;db.get(LeavePolicy,1).allow_hr_override=True
    db.add(RoleAssignment(user_id=1,role='HR'));db.add(RoleAssignment(user_id=3,role='MANAGER'));db.commit()
    rid=client.post('/api/v1/requests',json=payload()).json()['id']
    assert client.post(f'/api/v1/requests/{rid}/approve',json={'override_reason':'Exception'}).status_code==403

def test_quota_and_policy_update(client,db):
    db.get(MobilePolicy,1).monthly_limit=1;db.commit()
    assert client.post('/api/v1/requests',json=payload('MOBILE')).status_code==201
    second=payload('MOBILE',start=next_monday()+timedelta(days=1))
    assert client.post('/api/v1/requests',json=second).status_code==409
    assert client.post('/api/v1/policies',json={'kind':'mobile','config':{'name':'Bad privilege'}}).status_code==403
    sign_in(db,3)
    assert client.patch('/api/v1/policies/1',json={'kind':'mobile','config':{'name':'Flexible','monthly_limit':2}}).status_code==200
    sign_in(db,2)
    assert client.post('/api/v1/requests',json=second).status_code==201

def test_international_review(client,db):
    rid=client.post('/api/v1/requests',json=payload('MOBILE',location_type='ABROAD',city='Paris',country='FR')).json()['id'];sign_in(db,1)
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).status_code==403
    sign_in(db,3)
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).status_code==422
    response=client.post(f'/api/v1/requests/{rid}/approve',json={'override_reason':'Reviewed by People Operations'})
    assert response.status_code==200,response.text

def test_withdraw_releases_conflicts(client):
    rid=client.post('/api/v1/requests',json=payload()).json()['id']
    assert client.post(f'/api/v1/requests/{rid}/withdraw',json={}).status_code==200
    assert client.post('/api/v1/requests',json=payload('MOBILE')).status_code==201

def test_crossyear_debits(db):
    employee=db.get(User,2);manager=db.get(User,1);year=date.today().year
    db.get(WorkSchedule,1).weekdays=list(range(7));db.get(WorkSchedule,1).work_on_holidays=True
    req=requests.create(db,employee,RequestInput(**payload(start=date(year,12,31),end=date(year+1,1,1))))
    requests.transition(db,manager,req.id,'approve',Decision());db.flush()
    ledger=list(db.scalars(select(Ledger).where(Ledger.related_request_id==req.id)))
    assert [(e.year,e.amount) for e in ledger]==[(year,Decimal('-1')),(year+1,Decimal('-1'))]

def test_holiday_and_custom_schedule_preview(client,db):
    day=next_monday();db.add(Holiday(calendar_id=1,date=day,name='Company day'));db.commit()
    assert client.post('/api/v1/requests/preview',json=payload()).status_code==422
    db.get(WorkSchedule,1).weekdays=[5];db.commit()
    assert Decimal(client.post('/api/v1/requests/preview',json=payload(start=day+timedelta(days=5))).json()['days'])==1

def test_expired_carryover_and_reversal(db):
    employee=db.get(User,2);manager=db.get(User,1);year=date.today().year+1
    list(db.scalars(select(Ledger).where(Ledger.employee_id==2,Ledger.year==year)))[0].amount=0
    db.add(Ledger(employee_id=2,leave_type_id=1,year=year,effective_date=date(year,1,1),expires_on=date(year,3,31),amount=2,transaction_type='CARRYOVER',reason='Test',created_by=1,idempotency_key='carry-test'))
    db.get(WorkSchedule,1).weekdays=list(range(7));db.get(WorkSchedule,1).work_on_holidays=True;db.flush()
    req=requests.create(db,employee,RequestInput(**payload(start=date(year,2,1))))
    requests.transition(db,manager,req.id,'approve',Decision());db.flush()
    assert balances.balance(db,2,1,year,date(year,2,1))==1
    requests.transition(db,employee,req.id,'cancel',Decision());requests.transition(db,manager,req.id,'approve',Decision());db.flush()
    assert balances.balance(db,2,1,year,date(year,2,1))==2
    assert balances.balance(db,2,1,year,date(year,4,1))==0

def test_idempotent_entitlement(db):
    grant=Entitlement(leave_type_id=1,year=date.today().year+2,reason='Annual grant')
    assert balances.entitlement(db,db.get(User,3),2,grant).id==balances.entitlement(db,db.get(User,3),2,grant).id

def test_settings_and_role_escalation(client,db):
    assert client.patch('/api/v1/settings',json={'name':'Oops','retention_years':5}).status_code==403
    sign_in(db,3)
    assert client.patch('/api/v1/employees/2',json={'roles':['EMPLOYEE','ADMIN']}).status_code==403
    assert client.patch('/api/v1/employees/2',json={'identity_provider_subject':'attacker'}).status_code==403


def test_remove_and_restore_employee_preserves_history(client,db):
    sign_in(db,5)
    request_id=client.post('/api/v1/requests',json=payload()).json()['id']
    ledger_count=len(list(db.scalars(select(Ledger).where(Ledger.employee_id==5))))
    sign_in(db,4)
    assert client.patch('/api/v1/employees/4',json={'status':'INACTIVE'}).status_code==422
    assert client.patch('/api/v1/employees/1',json={'status':'INACTIVE'}).status_code==422
    response=client.patch('/api/v1/employees/5',json={'status':'INACTIVE'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='INACTIVE'
    assert not any(e['id']==5 for e in client.get('/api/v1/employees',params={'status':'ACTIVE'}).json()['items'])
    assert any(e['id']==5 for e in client.get('/api/v1/employees',params={'status':'INACTIVE'}).json()['items'])
    assert db.get(Request,request_id).employee_id==5
    assert len(list(db.scalars(select(Ledger).where(Ledger.employee_id==5))))==ledger_count
    assert client.patch('/api/v1/employees/5',json={'status':'ACTIVE'}).json()['status']=='ACTIVE'
    assert any(e['id']==5 for e in client.get('/api/v1/employees',params={'status':'ACTIVE'}).json()['items'])


def test_manager_choices_include_only_active_managers(client,db):
    managers=client.get('/api/v1/managers').json()
    assert {manager['id'] for manager in managers}=={1}
    assert managers[0]['first_name']==db.get(User,1).first_name
    db.get(User,1).status='INACTIVE'
    db.commit()
    assert client.get('/api/v1/managers').json()==[]


def test_admin_can_delete_only_unused_departments(client,db):
    sign_in(db,2)
    assert client.delete('/api/v1/departments/1').status_code==403
    sign_in(db,4)
    assert client.delete('/api/v1/departments/1').status_code==409
    response=client.post('/api/v1/departments',json={'name':'Temporary','description':''})
    assert response.status_code==201,response.text
    department_id=response.json()['id']
    response=client.post('/api/v1/teams',json={'name':'Temporary team','department_id':department_id})
    assert response.status_code==201,response.text
    team_id=response.json()['id']
    assert client.delete(f'/api/v1/departments/{department_id}').status_code==204
    assert db.get(Department,department_id) is None
    assert db.get(Team,team_id) is None

def test_reject_cancellation_keeps_usage(client,db):
    rid=client.post('/api/v1/requests',json=payload()).json()['id'];sign_in(db,1)
    client.post(f'/api/v1/requests/{rid}/approve',json={});sign_in(db,2)
    client.post(f'/api/v1/requests/{rid}/cancel',json={});sign_in(db,1)
    assert client.post(f'/api/v1/requests/{rid}/reject',json={'comment':'Already taken'}).json()['status']=='APPROVED'
    assert sum(e.amount for e in db.scalars(select(Ledger).where(Ledger.related_request_id==rid)))==-1

def test_crossyear_insufficient_second_year_rolls_back_first(client,db):
    year=date.today().year
    db.get(WorkSchedule,1).weekdays=list(range(7));db.get(WorkSchedule,1).work_on_holidays=True
    for entry in db.scalars(select(Ledger).where(Ledger.employee_id==2,Ledger.year==year+1)): entry.amount=0
    db.commit()
    rid=client.post('/api/v1/requests',json=payload(start=date(year,12,31),end=date(year+1,1,1))).json()['id'];sign_in(db,1)
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).status_code==409
    assert not list(db.scalars(select(Ledger).where(Ledger.related_request_id==rid)))
    assert db.get(Request,rid).status=='PENDING'

def test_no_approval_policy_uses_same_ledger(client,db):
    from app.models.entities import LeaveType
    db.get(LeaveType,1).approval_required=False;db.commit()
    request=client.post('/api/v1/requests',json=payload()).json()
    assert request['status']=='APPROVED'
    assert request['decisions'][0]['decision']=='SYSTEM_APPROVED'
    assert sum(e.amount for e in db.scalars(select(Ledger).where(Ledger.related_request_id==request['id'])))==-1

def test_hr_override_requires_policy_and_reason(client,db):
    for e in db.scalars(select(Ledger).where(Ledger.employee_id==2)): e.amount=0
    db.commit();rid=client.post('/api/v1/requests',json=payload()).json()['id'];sign_in(db,3)
    assert client.post(f'/api/v1/requests/{rid}/approve',json={'override_reason':'Urgent exception'}).status_code==403
    db.get(LeavePolicy,1).allow_hr_override=True;db.commit()
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).status_code==422
    assert client.post(f'/api/v1/requests/{rid}/approve',json={'override_reason':'Urgent exception'}).status_code==200

def test_draft_submission_withdrawal_and_invalid_transition(client,db):
    rid=client.post('/api/v1/requests',json=payload(submit=False)).json()['id']
    assert client.post(f'/api/v1/requests/{rid}/cancel',json={}).status_code==409
    assert client.post(f'/api/v1/requests/{rid}/submit',json={}).json()['status']=='PENDING'
    assert client.post(f'/api/v1/requests/{rid}/submit',json={}).status_code==409
    assert client.post(f'/api/v1/requests/{rid}/withdraw',json={}).json()['status']=='CANCELLED'

def test_hr_adjustment_idempotency(client,db):
    sign_in(db,3)
    body={'leave_type_id':1,'year':date.today().year,'amount':'2.5','reason':'Contractual allowance adjustment','idempotency_key':'test-key-1234'}
    first=client.post('/api/v1/employees/2/adjustments',json=body)
    assert first.status_code==200,first.text
    assert first.json()['id']==client.post('/api/v1/employees/2/adjustments',json=body).json()['id']
    body['amount']='4'
    assert client.post('/api/v1/employees/2/adjustments',json=body).status_code==409

def test_notification_ownership_and_delivery_outbox(client,db):
    from app.models.entities import EmailDelivery
    client.post('/api/v1/requests',json=payload());sign_in(db,1)
    notifications=client.get('/api/v1/notifications').json()
    assert notifications and list(db.scalars(select(EmailDelivery)))
    sign_in(db,2)
    assert client.post(f"/api/v1/notifications/{notifications[0]['id']}/read").status_code==404

def test_private_reasons_are_not_in_audit(client,db):
    rid=client.post('/api/v1/requests',json=payload(comment='Sensitive comment')).json()['id'];sign_in(db,1)
    client.post(f'/api/v1/requests/{rid}/reject',json={'comment':'Private decision'});sign_in(db,4)
    text=client.get('/api/v1/audit').text
    assert 'Sensitive comment' not in text and 'Private decision' not in text

def test_country_weekday_advance_notice_rules(client,db):
    policy=db.get(MobilePolicy,1);policy.restricted_countries=['FR'];db.commit()
    assert client.post('/api/v1/requests',json=payload('MOBILE',location_type='ABROAD',country='FR',city='Paris')).status_code==409
    policy.allowed_weekdays=[1,2,3,4];db.commit()
    assert client.post('/api/v1/requests',json=payload('MOBILE')).status_code==409
    policy.allowed_weekdays=[0,1,2,3,4];policy.advance_notice_days=90;db.commit()
    assert client.post('/api/v1/requests',json=payload('MOBILE')).status_code==409

def test_off_team_calendar_filter_cannot_expand_visibility(client,db):
    response=client.get('/api/v1/calendar',params={'start':str(next_monday()),'end':str(next_monday()),'team_id':2})
    assert response.status_code==200 and response.json()['employees']==[]

def test_deactivated_employee_cannot_be_approved(client,db):
    rid=client.post('/api/v1/requests',json=payload()).json()['id']
    db.get(User,2).status='INACTIVE';db.commit();sign_in(db,1)
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).status_code==422

def test_monthly_accrual_rounds_to_exact_annual_allowance(db):
    db.get(LeavePolicy,1).accrual_frequency='MONTHLY';db.flush()
    year=date.today().year+2
    for month in range(1,13): balances.entitlement(db,db.get(User,3),2,Entitlement(leave_type_id=1,year=year,month=month,reason='Monthly accrual'))
    assert sum(e.amount for e in db.scalars(select(Ledger).where(Ledger.employee_id==2,Ledger.year==year)))==Decimal('25')

def test_partial_policy_update_preserves_existing_rules(client,db):
    policy=db.get(MobilePolicy,1);policy.advance_notice_days=4;policy.weekly_limit=2;db.commit();sign_in(db,3)
    response=client.patch('/api/v1/policies/1',json={'kind':'mobile','config':{'monthly_limit':10}})
    assert response.status_code==200,response.text
    assert response.json()['advance_notice_days']==4 and Decimal(response.json()['weekly_limit'])==2

def test_mobile_approval_and_cancellation_restore_quota(client,db):
    rid=client.post('/api/v1/requests',json=payload('MOBILE')).json()['id'];sign_in(db,1)
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).status_code==200
    assert not list(db.scalars(select(Ledger).where(Ledger.related_request_id==rid)))
    sign_in(db,2)
    assert client.post(f'/api/v1/requests/{rid}/cancel',json={}).status_code==200
    sign_in(db,1)
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).json()['status']=='CANCELLED'
    sign_in(db,2)
    assert client.post('/api/v1/requests',json=payload('MOBILE')).status_code==201

def test_funded_overdraft_can_be_used_again(client,db):
    for e in db.scalars(select(Ledger).where(Ledger.employee_id==2)): e.amount=0
    db.get(LeavePolicy,1).allow_hr_override=True;db.commit()
    rid=client.post('/api/v1/requests',json=payload()).json()['id'];sign_in(db,3)
    assert client.post(f'/api/v1/requests/{rid}/approve',json={'override_reason':'Authorized overdraft'}).status_code==200
    assert client.post('/api/v1/employees/2/adjustments',json={'leave_type_id':1,'year':next_monday().year,'amount':2,'reason':'Additional contractual days','idempotency_key':'fund-overdraft'}).status_code==200
    sign_in(db,2)
    rid=client.post('/api/v1/requests',json=payload(start=next_monday()+timedelta(days=1))).json()['id'];sign_in(db,1)
    assert client.post(f'/api/v1/requests/{rid}/approve',json={}).status_code==200
