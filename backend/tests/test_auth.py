import time
from types import SimpleNamespace
from unittest.mock import patch
import pytest
jwt = pytest.importorskip('jwt', reason='PyJWT required for signature validation tests')
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.security import HTTPAuthorizationCredentials
from app.core.auth import current_user
from app.core.config import Settings
from app.core.errors import DomainError
from app.models.entities import User


@pytest.fixture
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def clerk_config(db, monkeypatch):
    config = Settings(clerk_issuer='https://test.clerk.accounts.dev')
    db.get(User, 2).identity_provider_subject = 'user_employee'
    db.flush()
    monkeypatch.setattr('app.core.auth.settings', lambda: config)
    return config


def claims(config, **changes):
    now = int(time.time())
    return {'sub': 'user_employee', 'sid': 'sess_example', 'azp': 'http://localhost:3000',
            'iss': config.clerk_issuer, 'exp': now + 60, 'iat': now, 'nbf': now - 5, **changes}


def authenticate(db, signing_key, payload):
    token = jwt.encode(payload, signing_key, algorithm='RS256')
    with patch('app.core.auth.jwks_client') as client:
        client.return_value.get_signing_key_from_jwt.return_value = SimpleNamespace(key=signing_key.public_key())
        return current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token), db)


@pytest.mark.parametrize('change', [{'iss':'https://attacker.invalid'}, {'exp':1}, {'sub':'user_unknown'},
                                    {'azp':'https://attacker.invalid'}, {'nbf':4102444800}, {'sts':'pending'}])
def test_invalid_signed_claims_are_rejected(db, signing_key, clerk_config, change):
    with pytest.raises(DomainError): authenticate(db, signing_key, claims(clerk_config, **change))


def test_standard_session_without_aud_and_inactive_employee(db, signing_key, clerk_config):
    assert authenticate(db, signing_key, claims(clerk_config)).id == 2
    db.get(User, 2).status = 'INACTIVE'; db.flush()
    with pytest.raises(DomainError): authenticate(db, signing_key, claims(clerk_config))


def test_optional_audience_is_enforced_when_configured(db, signing_key, clerk_config):
    clerk_config.clerk_audience = 'workleave-api'
    with pytest.raises(DomainError): authenticate(db, signing_key, claims(clerk_config))
    with pytest.raises(DomainError): authenticate(db, signing_key, claims(clerk_config, aud='other-api'))
    assert authenticate(db, signing_key, claims(clerk_config, aud='workleave-api')).id == 2


@pytest.mark.parametrize('field', ['exp', 'iat', 'nbf', 'iss', 'sub', 'sid', 'azp'])
def test_required_session_claims(db, signing_key, clerk_config, field):
    payload = claims(clerk_config); payload.pop(field)
    with pytest.raises(DomainError): authenticate(db, signing_key, payload)


def test_forged_signature(db, signing_key, clerk_config):
    token = jwt.encode(claims(clerk_config), rsa.generate_private_key(public_exponent=65537, key_size=2048), algorithm='RS256')
    with patch('app.core.auth.jwks_client') as client:
        client.return_value.get_signing_key_from_jwt.return_value = SimpleNamespace(key=signing_key.public_key())
        with pytest.raises(DomainError): current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token), db)
