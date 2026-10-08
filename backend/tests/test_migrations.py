from pathlib import Path
import pytest
alembic=pytest.importorskip('alembic.config',reason='Alembic required for migration round-trip test')
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from app.core.config import settings

def test_fresh_migration_and_roundtrip(tmp_path,monkeypatch):
    url='sqlite:///'+str(tmp_path/'migration.db')
    monkeypatch.setenv('DATABASE_URL',url);settings.cache_clear()
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    try:
        command.upgrade(config,'head')
        engine=create_engine(url)
        assert 'leave_balance_ledger' in inspect(engine).get_table_names()
        assert 'request_days' in inspect(engine).get_table_names()
        engine.dispose()
        command.downgrade(config,'base');command.upgrade(config,'head')
    finally: settings.cache_clear()
