from functools import lru_cache
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import get_db
from app.core.errors import DomainError, require
from app.models.entities import RoleAssignment, User

bearer = HTTPBearer(auto_error=False)


@lru_cache
def jwks_client():
    import jwt
    return jwt.PyJWKClient(settings().clerk_jwks_url, cache_keys=False, lifespan=300, timeout=5)


def validate_session_claims(claims, config):
    if claims.get('azp') not in config.clerk_authorized_parties:
        raise ValueError('Untrusted authorized party')
    if not isinstance(claims.get('sub'), str) or not claims['sub'].startswith('user_'):
        raise ValueError('Expected a Clerk user session')
    if not isinstance(claims.get('sid'), str) or not claims['sid'].startswith('sess_'):
        raise ValueError('Expected a Clerk session ID')
    if claims.get('sts') not in (None, 'active') or claims.get('act') is not None:
        raise ValueError('Pending and impersonated sessions are not accepted')


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    require(credentials is not None, 'Authentication required', 'unauthorized', 401)
    config = settings()
    require(bool(config.clerk_issuer), 'Clerk authentication is not configured', 'authentication_unavailable', 503)
    import jwt
    try:
        key = jwks_client().get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(credentials.credentials, key.key, algorithms=['RS256'],
                            audience=config.clerk_audience, issuer=config.clerk_issuer,
                            options={'verify_aud': bool(config.clerk_audience),
                                     'require': ['exp', 'iat', 'nbf', 'iss', 'sub', 'sid', 'azp'] + (['aud'] if config.clerk_audience else [])})
        validate_session_claims(claims, config)
    except jwt.PyJWKClientConnectionError:
        raise DomainError('Clerk signing keys are temporarily unavailable', 'authentication_unavailable', 503) from None
    except (jwt.PyJWTError, ValueError, TypeError):
        raise DomainError('Invalid or expired access token', 'unauthorized', 401) from None
    user = db.scalar(select(User).where(User.identity_provider_subject == claims['sub'], User.status == 'ACTIVE'))
    require(user is not None, 'No active employee account is linked to this Clerk user. Contact your administrator.', 'forbidden', 403)
    return user


def roles(db, user):
    return set(db.scalars(select(RoleAssignment.role).where(RoleAssignment.user_id == user.id)))


def has_role(db, user, *allowed):
    return bool(roles(db, user) & set(allowed))


def authorize(db, user, *allowed):
    require(has_role(db, user, *allowed), 'You do not have permission for this action', 'forbidden', 403)
