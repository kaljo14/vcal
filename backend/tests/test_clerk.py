from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.core.auth import validate_session_claims, current_user
from app.core.config import Settings
from app.core.errors import DomainError
from app.migrate_identities import IdentityLink, migrate_identities
from app.models.entities import User, Ledger, AuditLog
from sqlalchemy import select


def claims(**changes):
    return {'sub': 'user_employee', 'sid': 'sess_example', 'azp': 'http://localhost:3000', **changes}


def test_standard_session_without_audience():
    config = Settings(clerk_issuer='https://example.clerk.accounts.dev')
    assert config.clerk_audience is None
    assert config.clerk_jwks_url == 'https://example.clerk.accounts.dev/.well-known/jwks.json'
    validate_session_claims(claims(), config)


@pytest.mark.parametrize('change', [
    {'azp': 'https://attacker.invalid'}, {'azp': None}, {'azp': 'http://localhost:3000.attacker.invalid'},
    {'sub': 'old-provider-uuid'}, {'sid': ''}, {'sid': None}, {'sts': 'pending'},
    {'act': {'sub': 'user_impersonator'}},
])
def test_unsafe_session_claims_rejected(change):
    with pytest.raises(ValueError): validate_session_claims(claims(**change), Settings())


@pytest.mark.parametrize('options', [
    {'clerk_issuer': 'http://insecure.example.com'},
    {'clerk_issuer': 'https://example.com/another/path'},
    {'clerk_authorized_parties': ['*']}, {'clerk_authorized_parties': []},
    {'environment': 'production', 'clerk_issuer': 'https://example.com'},
])
def test_configuration_rejects_unsafe_origins(options):
    with pytest.raises(ValidationError): Settings(**options)


def test_unconfigured_clerk_fails_closed(db, monkeypatch):
    monkeypatch.setattr('app.core.auth.settings', lambda: Settings())
    with pytest.raises(DomainError) as exc: current_user(SimpleNamespace(credentials='ignored'), db)
    assert exc.value.status == 503


def mapping(employee, target='user_newemployee'):
    return IdentityLink(employee_number=employee.employee_number, current_subject=employee.identity_provider_subject, clerk_user_id=target)


def test_identity_migration_is_dry_run_by_default(db):
    employee = db.get(User, 2); before = employee.identity_provider_subject
    assert migrate_identities(db, [mapping(employee)]) == ['WL-002']
    assert employee.identity_provider_subject == before


def test_identity_migration_preserves_employee_and_ledger(db):
    employee = db.get(User, 2)
    ledger = [(e.id, e.amount) for e in db.scalars(select(Ledger).where(Ledger.employee_id == 2))]
    link = mapping(employee)
    migrate_identities(db, [link], apply=True)
    assert employee.id == 2 and employee.identity_provider_subject == 'user_newemployee'
    assert ledger == [(e.id, e.amount) for e in db.scalars(select(Ledger).where(Ledger.employee_id == 2))]
    assert db.scalar(select(AuditLog).where(AuditLog.action == 'CLERK_IDENTITY_LINKED'))
    assert migrate_identities(db, [link], apply=True) == []


def test_identity_migration_rejects_stale_mapping_without_partial_writes(db):
    first, second = db.get(User, 2), db.get(User, 3)
    before = first.identity_provider_subject
    bad = IdentityLink(employee_number=second.employee_number, current_subject='wrong', clerk_user_id='user_second')
    with pytest.raises(DomainError): migrate_identities(db, [mapping(first), bad], apply=True)
    assert first.identity_provider_subject == before


def test_identity_migration_rejects_duplicate_target(db):
    with pytest.raises(DomainError): migrate_identities(db, [mapping(db.get(User, 2)), mapping(db.get(User, 3))], apply=True)
