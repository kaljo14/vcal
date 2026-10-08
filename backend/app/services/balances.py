import calendar
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from app.core.errors import require
from app.models.entities import Ledger, LedgerAllocation, LeavePolicy, LeaveType, Request, RequestDay
from app.services.common import audit, local_today, lock_employee

ZERO = Decimal('0')


def lots(db, employee_id, leave_type_id, year):
    entries = list(db.scalars(select(Ledger).where(Ledger.employee_id == employee_id, Ledger.leave_type_id == leave_type_id, Ledger.year == year).order_by(Ledger.id)))
    reversed_keys = {e.idempotency_key.removeprefix('reversal:') for e in entries if e.transaction_type == 'REVERSAL'}
    debits = [e for e in entries if e.amount < 0 and str(e.id) not in reversed_keys]
    debit_ids = [e.id for e in debits]
    allocations = list(db.scalars(select(LedgerAllocation).where(LedgerAllocation.debit_id.in_(debit_ids)))) if debit_ids else []
    credits = [(e, e.amount - sum((a.amount for a in allocations if a.credit_id == e.id), ZERO)) for e in entries if e.amount > 0 and e.transaction_type != 'REVERSAL']
    debt = sum((-e.amount for e in debits), ZERO) - sum((a.amount for a in allocations), ZERO)
    return sorted(credits, key=lambda pair: (pair[0].expires_on or date.max, pair[0].effective_date, pair[0].id)), debt


def balance(db, employee_id, leave_type_id, year, on=None):
    on = on or date(year, 12, 31)
    credits, debt = lots(db, employee_id, leave_type_id, year)
    return sum((available for entry, available in credits if entry.effective_date <= on and (not entry.expires_on or entry.expires_on >= on)), ZERO) - debt


def debit_days(db, employee, leave_type_id, request, days, actor, override=False):
    """Consume earliest-expiring credit lots valid on each absence date."""
    for year in sorted({d[0].year for d in days}):
        credits, debt = lots(db, employee.id, leave_type_id, year)
        available = {e.id: amount for e, amount in credits}
        allocations = {}
        year_days = [d for d in days if d[0].year == year]
        for day, amount, _ in year_days:
            funded = sum((available[credit.id] for credit, _ in credits if credit.effective_date <= day and (not credit.expires_on or credit.expires_on >= day)), ZERO) - debt
            require(override or funded >= amount, f'Insufficient leave balance for {year}', 'insufficient_balance', 409)
            remaining = amount
            for credit, _ in credits:
                if credit.effective_date <= day and (not credit.expires_on or credit.expires_on >= day):
                    consumed = min(available[credit.id], remaining)
                    if consumed > 0:
                        available[credit.id] -= consumed
                        allocations[credit.id] = allocations.get(credit.id, ZERO) + consumed
                        remaining -= consumed
            require(override or remaining == 0, f'Insufficient leave balance for {year}', 'insufficient_balance', 409)
        entry = Ledger(employee_id=employee.id, leave_type_id=leave_type_id, year=year, effective_date=min(d[0] for d in year_days), amount=-sum((d[1] for d in year_days), ZERO), transaction_type='DEBIT', related_request_id=request.id, reason='Approved leave', created_by=actor.id, idempotency_key=f'debit:{request.id}:{year}')
        db.add(entry)
        db.flush()
        for credit_id, amount in allocations.items():
            db.add(LedgerAllocation(debit_id=entry.id, credit_id=credit_id, amount=amount))
        db.flush()


def reverse_request(db, request, actor):
    for debit in db.scalars(select(Ledger).where(Ledger.related_request_id == request.id, Ledger.transaction_type == 'DEBIT')):
        db.add(Ledger(employee_id=debit.employee_id, leave_type_id=debit.leave_type_id, year=debit.year, effective_date=local_today(actor), amount=-debit.amount, transaction_type='REVERSAL', related_request_id=request.id, reason='Approved cancellation', created_by=actor.id, idempotency_key=f'reversal:{debit.id}'))


def summary(db, employee, year):
    result = []
    on = min(max(local_today(employee), date(year, 1, 1)), date(year, 12, 31))
    for leave_type in db.scalars(select(LeaveType).where(LeaveType.tracks_balance.is_(True))):
        from app.models.entities import LeaveDetail
        rows = db.execute(select(RequestDay.day_fraction, Request.status).join(Request, Request.id == RequestDay.request_id).join(LeaveDetail, LeaveDetail.request_id == Request.id).where(Request.employee_id == employee.id, LeaveDetail.leave_type_id == leave_type.id, RequestDay.date >= date(year, 1, 1), RequestDay.date <= date(year, 12, 31))).all()
        approved = sum((amount for amount, status in rows if status in ('APPROVED', 'CANCELLATION_REQUESTED')), ZERO)
        pending = sum((amount for amount, status in rows if status == 'PENDING'), ZERO)
        entries = list(db.scalars(select(Ledger).where(Ledger.employee_id == employee.id, Ledger.leave_type_id == leave_type.id, Ledger.year == year)))
        result.append(dict(leave_type_id=leave_type.id, name=leave_type.name, year=year, available=balance(db, employee.id, leave_type.id, year, on), used=approved, pending=pending, granted=sum((e.amount for e in entries if e.amount > 0 and e.transaction_type != 'REVERSAL'), ZERO), projected=balance(db, employee.id, leave_type.id, year, on)-pending))
    return result


def adjustment(db, actor, employee_id, data):
    employee = lock_employee(db, employee_id)
    require(db.get(LeaveType, data.leave_type_id), 'Leave type not found')
    key = f'adjust:{employee_id}:{data.idempotency_key}'
    existing = db.scalar(select(Ledger).where(Ledger.idempotency_key == key))
    if existing:
        require(existing.amount == data.amount and existing.year == data.year and existing.leave_type_id == data.leave_type_id and existing.reason == data.reason, 'Idempotency key already used with different values', 'conflict', 409)
        return existing
    require(data.amount != 0, 'Adjustment must not be zero')
    effective = data.effective_date or date(data.year, 1, 1)
    require(effective.year == data.year, 'Effective date must be in the balance year')
    entry = Ledger(employee_id=employee.id, leave_type_id=data.leave_type_id, year=data.year, amount=data.amount, transaction_type='ADJUSTMENT', effective_date=effective, reason=data.reason, created_by=actor.id, idempotency_key=key)
    if data.amount < 0:
        credits, debt = lots(db, employee.id, data.leave_type_id, data.year)
        require(balance(db, employee.id, data.leave_type_id, data.year, effective) >= -data.amount, 'Adjustment would produce an unfunded balance')
        db.add(entry)
        db.flush()
        remaining = -data.amount
        for credit, available in credits:
            if credit.effective_date <= effective and (not credit.expires_on or credit.expires_on >= effective):
                amount = min(available, remaining)
                if amount > 0:
                    db.add(LedgerAllocation(debit_id=entry.id, credit_id=credit.id, amount=amount))
                    remaining -= amount
    else:
        db.add(entry)
    db.flush()
    audit(db, actor, 'BALANCE_ADJUSTED', 'ledger', entry.id, reason=data.reason, amount=str(data.amount))
    return entry


def entitlement(db, actor, employee_id, data, carryover=False):
    employee = lock_employee(db, employee_id)
    policy = db.get(LeavePolicy, employee.leave_policy_id)
    leave_type = db.get(LeaveType, data.leave_type_id)
    require(leave_type and leave_type.tracks_balance, 'Choose a balance-tracked leave type')
    month = data.month if policy.accrual_frequency == 'MONTHLY' and not carryover else 1
    effective = date(data.year, month, 1)
    require(effective >= policy.valid_from and (not policy.valid_until or effective <= policy.valid_until), 'Policy is not valid for this date')
    key = f'{"carryover" if carryover else "entitlement"}:{employee_id}:{data.leave_type_id}:{data.year}:{month}'
    existing = db.scalar(select(Ledger).where(Ledger.idempotency_key == key))
    if existing:
        return existing
    amount = policy.annual_allowance
    if policy.accrual_frequency == 'MONTHLY':
        amount = (policy.annual_allowance * month / 12).quantize(Decimal('0.01')) - (policy.annual_allowance * (month - 1) / 12).quantize(Decimal('0.01'))
    expiry = None
    if carryover:
        require(data.year <= local_today(employee).year, 'Carryover can only run after the source year ends')
        amount = max(ZERO, min(policy.carryover_limit, balance(db, employee.id, data.leave_type_id, data.year-1, date(data.year-1, 12, 31))))
        # Lock the source amount so a second transfer or historical approval cannot consume it.
        from app.schemas.contracts import Adjustment
        if amount > 0:
            adjustment(db, actor, employee_id, Adjustment(leave_type_id=data.leave_type_id, year=data.year-1, amount=-amount, effective_date=date(data.year-1, 12, 31), reason='Carryover transfer to next year', idempotency_key=f'carryover-transfer-{data.leave_type_id}-{data.year}'))
        if policy.carryover_expiry_month:
            expiry = date(data.year, policy.carryover_expiry_month, calendar.monthrange(data.year, policy.carryover_expiry_month)[1])
    entry = Ledger(employee_id=employee.id, leave_type_id=data.leave_type_id, year=data.year, effective_date=effective, expires_on=expiry, amount=amount, transaction_type='CARRYOVER' if carryover else 'ACCRUAL', reason=data.reason, created_by=actor.id, idempotency_key=key)
    db.add(entry)
    db.flush()
    audit(db, actor, 'CARRYOVER' if carryover else 'ENTITLEMENT_GRANTED', 'ledger', entry.id, amount=str(amount), reason=data.reason)
    return entry
