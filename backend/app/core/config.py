from functools import lru_cache
import os
import json
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, model_validator
from dotenv import load_dotenv


def valid_origin(value, https_only=False):
    parsed = urlsplit(value)
    return (parsed.scheme in (['https'] if https_only else ['http', 'https'])
            and bool(parsed.hostname) and not parsed.username and not parsed.password
            and parsed.path in ('', '/') and not parsed.query and not parsed.fragment
            and '*' not in value and not any(c.isspace() for c in value))


class Settings(BaseModel):
    model_config = ConfigDict(extra='ignore')
    environment: str = 'development'
    database_url: str = 'postgresql+psycopg://workleave:workleave@localhost:5432/workleave'
    clerk_issuer: str = ''
    # Standard Clerk session tokens have no aud claim; configure only when adding a custom aud.
    clerk_audience: str | None = None
    clerk_authorized_parties: list[str] = ['http://localhost:5173', 'http://localhost:3000']
    cors_origins: list[str] = ['http://localhost:5173', 'http://localhost:3000']
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    smtp_starttls: bool = True
    smtp_from: str = 'workleave@localhost'
    rate_limit_per_minute: int = 120

    @property
    def clerk_jwks_url(self):
        return self.clerk_issuer.rstrip('/') + '/.well-known/jwks.json'

    @model_validator(mode='after')
    def authentication_settings(self):
        self.clerk_issuer = self.clerk_issuer.rstrip('/')
        self.clerk_audience = self.clerk_audience or None
        if self.clerk_issuer and not valid_origin(self.clerk_issuer, https_only=True):
            raise ValueError('CLERK_ISSUER must be the exact HTTPS Clerk Frontend API origin')
        if not self.clerk_authorized_parties or any(not valid_origin(v) or v.endswith('/') for v in self.clerk_authorized_parties):
            raise ValueError('CLERK_AUTHORIZED_PARTIES must contain explicit application origins without trailing slashes')
        if self.environment == 'production':
            if not self.clerk_issuer or any(not valid_origin(v, True) for v in self.clerk_authorized_parties + self.cors_origins):
                raise ValueError('Production requires a Clerk issuer and explicit HTTPS application origins')
            if not self.database_url.startswith('postgresql'):
                raise ValueError('Production requires PostgreSQL')
        return self


@lru_cache
def settings():
    load_dotenv()
    values = {name: os.environ[name.upper()] for name in Settings.model_fields if name.upper() in os.environ}
    for name in ('cors_origins', 'clerk_authorized_parties'):
        if name in values:
            values[name] = json.loads(values[name])
    return Settings(**values)
