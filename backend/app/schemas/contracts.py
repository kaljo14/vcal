from datetime import date
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, validate_default=True)


class RequestInput(StrictModel):
    kind: Literal['LEAVE', 'MOBILE']
    start_date: date
    end_date: date
    portion: Literal['FULL', 'AM', 'PM'] = 'FULL'
    leave_type_id: int | None = None
    location_type: Literal['HOME', 'OTHER', 'ABROAD'] = 'HOME'
    city: str = Field(default='', max_length=120)
    country: str = Field(default='', max_length=2)
    comment: str = Field(default='', max_length=1000)
    submit: bool = True

    @model_validator(mode='after')
    def validate_range(self):
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 366:
            raise ValueError('Choose an ordered date range of at most 367 days')
        if self.portion != 'FULL' and self.start_date != self.end_date:
            raise ValueError('Half-day requests must be a single day')
        if self.kind == 'LEAVE' and not self.leave_type_id:
            raise ValueError('Select a leave type')
        if self.kind == 'MOBILE' and self.location_type != 'HOME' and (not self.city or len(self.country) != 2):
            raise ValueError('City and two-letter country code are required for this location')
        if self.country and (not self.country.isalpha() or len(self.country) != 2):
            raise ValueError('Use a two-letter country code')
        self.country = self.country.upper()
        return self


class Decision(StrictModel):
    comment: str = Field(default='', max_length=1000)
    override_reason: str = Field(default='', max_length=1000)


class LeavePolicyInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    annual_allowance: Decimal = Field(default=25, ge=0, le=366)
    carryover_limit: Decimal = Field(default=5, ge=0, le=366)
    carryover_expiry_month: int | None = Field(default=3, ge=1, le=12)
    accrual_frequency: Literal['ANNUAL', 'MONTHLY'] = 'ANNUAL'
    allow_hr_override: bool = False
    valid_from: date = date(2020, 1, 1)
    valid_until: date | None = None

    @model_validator(mode='after')
    def validity(self):
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValueError('Policy validity end precedes start')
        return self


class MobilePolicyInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    monthly_limit: Decimal = Field(default=8, ge=0, le=31)
    weekly_limit: Decimal = Field(default=3, ge=0, le=7)
    allowed_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    advance_notice_days: int = Field(default=0, ge=0, le=365)
    restricted_countries: list[str] = Field(default_factory=list)
    allowed_locations: list[Literal['HOME', 'OTHER', 'ABROAD']] = Field(default_factory=lambda: ['HOME', 'OTHER', 'ABROAD'])
    approval_required: bool = True
    international_requires_hr: bool = True
    allow_hr_override: bool = False

    @field_validator('allowed_weekdays')
    @classmethod
    def weekdays(cls, value):
        if not value or len(set(value)) != len(value) or any(d < 0 or d > 6 for d in value):
            raise ValueError('Weekdays must be distinct integers from 0 to 6')
        return value

    @field_validator('restricted_countries')
    @classmethod
    def countries(cls, value):
        if any(len(c) != 2 or not c.isalpha() for c in value):
            raise ValueError('Use two-letter country codes')
        return [c.upper() for c in value]


class PolicyInput(StrictModel):
    kind: Literal['leave', 'mobile']
    config: dict

    @model_validator(mode='after')
    def config_schema(self):
        schema = LeavePolicyInput if self.kind == 'leave' else MobilePolicyInput
        self.config = schema.model_validate(self.config).model_dump(exclude_unset=True)
        return self


class PolicyPatch(StrictModel):
    kind: Literal['leave', 'mobile']
    config: dict


class EmployeeInput(StrictModel):
    identity_provider_subject: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    employee_number: str = Field(min_length=1, max_length=50)
    manager_id: int | None = None
    team_id: int
    department_id: int
    schedule_id: int
    leave_policy_id: int
    mobile_policy_id: int
    employment_start_date: date
    employment_end_date: date | None = None
    timezone: str = 'Europe/Sofia'
    status: Literal['ACTIVE', 'INACTIVE'] = 'ACTIVE'
    roles: list[Literal['EMPLOYEE', 'MANAGER', 'HR', 'ADMIN']] = Field(default_factory=lambda: ['EMPLOYEE'])

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError('Unknown IANA timezone') from None
        return value


class Adjustment(StrictModel):
    leave_type_id: int
    year: int = Field(ge=2000, le=2200)
    amount: Decimal = Field(max_digits=8, decimal_places=2)
    reason: str = Field(min_length=3, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=100)
    effective_date: date | None = None


class Entitlement(StrictModel):
    leave_type_id: int
    year: int = Field(ge=2000, le=2200)
    month: int = Field(default=1, ge=1, le=12)
    reason: str = Field(min_length=3, max_length=1000)


class HolidayInput(StrictModel):
    calendar_id: int
    date: date
    name: str = Field(min_length=1, max_length=200)


class DepartmentInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=500)


class TeamInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    department_id: int


class ScheduleInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    weekdays: list[int]
    hours_per_day: Decimal = Field(ge=1, le=24)
    holiday_calendar_id: int
    work_on_holidays: bool = False
    _weekdays = field_validator('weekdays')(MobilePolicyInput.weekdays.__func__)


class LeaveTypeInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    paid: bool = True
    tracks_balance: bool = True
    allow_half_day: bool = True
    approval_required: bool = True


class Preferences(StrictModel):
    email_notifications: bool


class SettingsInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    timezone: str = 'Europe/Sofia'
    retention_years: int = Field(ge=1, le=50)
    _timezone = field_validator('timezone')(EmployeeInput.valid_timezone.__func__)
