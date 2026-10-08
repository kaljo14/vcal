from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Department(Base):
    __tablename__ = 'departments'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(String(500), default='')


class Team(Base):
    __tablename__ = 'teams'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey('departments.id'))


class HolidayCalendar(Base):
    __tablename__ = 'holiday_calendars'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)


class Holiday(Base):
    __tablename__ = 'holidays'
    __table_args__ = (UniqueConstraint('calendar_id', 'date'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    calendar_id: Mapped[int] = mapped_column(ForeignKey('holiday_calendars.id'))
    date: Mapped[date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(200))


class WorkSchedule(Base):
    __tablename__ = 'work_schedules'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    weekdays: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4])
    hours_per_day: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=8)
    holiday_calendar_id: Mapped[int] = mapped_column(ForeignKey('holiday_calendars.id'))
    work_on_holidays: Mapped[bool] = mapped_column(Boolean, default=False)


class LeaveType(Base):
    __tablename__ = 'leave_types'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    paid: Mapped[bool] = mapped_column(Boolean, default=True)
    tracks_balance: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_half_day: Mapped[bool] = mapped_column(Boolean, default=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True)


class LeavePolicy(Base):
    __tablename__ = 'leave_policies'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    annual_allowance: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=25)
    carryover_limit: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=5)
    carryover_expiry_month: Mapped[int | None] = mapped_column(Integer, nullable=True, default=3)
    accrual_frequency: Mapped[str] = mapped_column(String(20), default='ANNUAL')
    allow_hr_override: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_from: Mapped[date] = mapped_column(Date, default=lambda: date(2020, 1, 1))
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)


class MobilePolicy(Base):
    __tablename__ = 'mobile_work_policies'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=8)
    weekly_limit: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=3)
    allowed_weekdays: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4])
    advance_notice_days: Mapped[int] = mapped_column(Integer, default=0)
    restricted_countries: Mapped[list] = mapped_column(JSON, default=list)
    allowed_locations: Mapped[list] = mapped_column(JSON, default=lambda: ['HOME', 'OTHER', 'ABROAD'])
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True)
    international_requires_hr: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_hr_override: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    identity_provider_subject: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    employee_number: Mapped[str] = mapped_column(String(50), unique=True)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey('teams.id'), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey('departments.id'))
    schedule_id: Mapped[int] = mapped_column(ForeignKey('work_schedules.id'))
    leave_policy_id: Mapped[int] = mapped_column(ForeignKey('leave_policies.id'))
    mobile_policy_id: Mapped[int] = mapped_column(ForeignKey('mobile_work_policies.id'))
    employment_start_date: Mapped[date] = mapped_column(Date)
    employment_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), default='Europe/Sofia')
    status: Mapped[str] = mapped_column(String(20), default='ACTIVE')
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint('manager_id IS NULL OR manager_id != id'), CheckConstraint("status IN ('ACTIVE','INACTIVE')"))


class RoleAssignment(Base):
    __tablename__ = 'role_assignments'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), primary_key=True)
    __table_args__ = (CheckConstraint("role IN ('EMPLOYEE','MANAGER','HR','ADMIN')"),)


class Request(Base):
    __tablename__ = 'requests'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    portion: Mapped[str] = mapped_column(String(4), default='FULL')
    status: Mapped[str] = mapped_column(String(30), default='DRAFT', index=True)
    comment: Mapped[str] = mapped_column(Text, default='')
    exception_flags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (CheckConstraint('end_date >= start_date'), CheckConstraint("kind IN ('LEAVE','MOBILE')"), CheckConstraint("portion IN ('FULL','AM','PM')"), CheckConstraint("status IN ('DRAFT','PENDING','APPROVED','REJECTED','CANCELLED','CANCELLATION_REQUESTED')"))


class LeaveDetail(Base):
    __tablename__ = 'leave_request_details'
    request_id: Mapped[int] = mapped_column(ForeignKey('requests.id'), primary_key=True)
    leave_type_id: Mapped[int] = mapped_column(ForeignKey('leave_types.id'))


class MobileDetail(Base):
    __tablename__ = 'mobile_request_details'
    request_id: Mapped[int] = mapped_column(ForeignKey('requests.id'), primary_key=True)
    location_type: Mapped[str] = mapped_column(String(10))
    city: Mapped[str] = mapped_column(String(120), default='')
    country: Mapped[str] = mapped_column(String(2), default='')


class RequestDay(Base):
    __tablename__ = 'request_days'
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey('requests.id'), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    day_fraction: Mapped[Decimal] = mapped_column(Numeric(2, 1))
    portion: Mapped[str] = mapped_column(String(4))
    __table_args__ = (UniqueConstraint('request_id', 'date'), CheckConstraint('day_fraction IN (0.5, 1.0)'))


class Ledger(Base):
    __tablename__ = 'leave_balance_ledger'
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    leave_type_id: Mapped[int] = mapped_column(ForeignKey('leave_types.id'))
    year: Mapped[int] = mapped_column(Integer)
    effective_date: Mapped[date] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    transaction_type: Mapped[str] = mapped_column(String(30))
    related_request_id: Mapped[int | None] = mapped_column(ForeignKey('requests.id'), nullable=True)
    reason: Mapped[str] = mapped_column(String(1000))
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index('ix_ledger_employee_type_year', 'employee_id', 'leave_type_id', 'year'),)


class LedgerAllocation(Base):
    __tablename__ = 'ledger_allocations'
    id: Mapped[int] = mapped_column(primary_key=True)
    debit_id: Mapped[int] = mapped_column(ForeignKey('leave_balance_ledger.id'))
    credit_id: Mapped[int] = mapped_column(ForeignKey('leave_balance_ledger.id'))
    amount: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    __table_args__ = (UniqueConstraint('debit_id', 'credit_id'), CheckConstraint('amount > 0'))


class Approval(Base):
    __tablename__ = 'approvals'
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey('requests.id'), index=True)
    approver_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    stage: Mapped[int] = mapped_column(Integer, default=1)
    decision: Mapped[str] = mapped_column(String(40))
    comment: Mapped[str] = mapped_column(String(1000), default='')
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    type: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(String(500))
    request_id: Mapped[int | None] = mapped_column(ForeignKey('requests.id'), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailDelivery(Base):
    __tablename__ = 'email_deliveries'
    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey('notifications.id'), unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default='PENDING', index=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class OrganizationSettings(Base):
    __tablename__ = 'organization_settings'
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(120), default='Workleave')
    timezone: Mapped[str] = mapped_column(String(80), default='Europe/Sofia')
    retention_years: Mapped[int] = mapped_column(Integer, default=5)
