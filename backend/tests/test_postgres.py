"""Real PostgreSQL locking and migration checks; no SQLite substitute."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from app.core.db import Base
from app.core.errors import DomainError
from app.models.entities import Ledger, Request, User, WorkSchedule
from app.schemas.contracts import Decision, RequestInput
from app.seed import seed
from app.services.requests import create, transition

@pytest.mark.postgres
def test_concurrent_approvals_cannot_overspend():
    url=os.getenv('TEST_DATABASE_URL')
    if not url: pytest.skip('TEST_DATABASE_URL required for PostgreSQL concurrency test')
    schema='test_'+uuid.uuid4().hex
    admin=create_engine(url)
    with admin.begin() as connection: connection.execute(text(f'CREATE SCHEMA {schema}'))
    engine=create_engine(url,connect_args={'options':f'-csearch_path={schema}'})
    sessions=sessionmaker(engine,expire_on_commit=False)
    try:
        Base.metadata.create_all(engine)
        with sessions.begin() as db:
            seed(db)
            for e in db.scalars(select(Ledger).where(Ledger.employee_id==2)): e.amount=1
            db.get(WorkSchedule,1).weekdays=list(range(7));db.get(WorkSchedule,1).work_on_holidays=True
            start=date.today()+timedelta(days=10)
            ids=[create(db,db.get(User,2),RequestInput(kind='LEAVE',start_date=start+timedelta(days=i),end_date=start+timedelta(days=i),leave_type_id=1)).id for i in range(2)]
        barrier=Barrier(2)
        def approve(rid):
            with sessions() as db:
                actor=db.get(User,1);barrier.wait(timeout=10)
                try:
                    transition(db,actor,rid,'approve',Decision());db.commit();return 'approved'
                except DomainError as error:
                    db.rollback();return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(approve,ids))
        assert sorted(results)==['approved','insufficient_balance']
        with sessions() as db:
            assert len(list(db.scalars(select(Request).where(Request.status=='APPROVED'))))==1
            assert sum(e.amount for e in db.scalars(select(Ledger).where(Ledger.related_request_id.in_(ids))))==Decimal('-1')
    finally:
        engine.dispose()
        with admin.begin() as connection: connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()
