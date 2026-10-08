import os
os.environ.setdefault('DATABASE_URL', 'sqlite://')
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.db import Base, get_db
from app.core.auth import current_user
from app.main import app
from app.seed import seed
from app.models.entities import User

@pytest.fixture
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)()
    seed(session); session.commit()
    yield session
    session.close(); engine.dispose()

@pytest.fixture
def client(db):
    def dependency():
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
    app.dependency_overrides[get_db] = dependency
    app.dependency_overrides[current_user] = lambda: db.get(User, 2)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

def sign_in(db, user_id):
    app.dependency_overrides[current_user] = lambda: db.get(User, user_id)
