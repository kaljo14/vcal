"""Explicit, atomic employee identity migration. Dry-run unless --apply is passed."""
import argparse
import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from app.core.db import SessionLocal
from app.core.errors import require
from app.models.entities import User
from app.services.common import audit


class IdentityLink(BaseModel):
    model_config = ConfigDict(extra='forbid')
    employee_number: str = Field(min_length=1)
    current_subject: str = Field(min_length=1)
    clerk_user_id: str = Field(pattern=r'^user_[A-Za-z0-9]+$')


def migrate_identities(db, mappings, apply=False):
    require(bool(mappings), 'Provide at least one identity mapping')
    require(len({m.employee_number for m in mappings}) == len(mappings), 'Duplicate employee numbers')
    require(len({m.clerk_user_id for m in mappings}) == len(mappings), 'Duplicate Clerk user IDs')
    # Match the same deterministic employee-lock order as policy/account administration.
    employees = list(db.scalars(select(User).order_by(User.id).with_for_update()))
    by_number = {u.employee_number: u for u in employees}
    by_subject = {u.identity_provider_subject: u for u in employees}
    changes = []
    for mapping in mappings:
        employee = by_number.get(mapping.employee_number)
        require(employee is not None, f'Unknown employee number: {mapping.employee_number}')
        if employee.identity_provider_subject == mapping.clerk_user_id:
            continue
        require(employee.identity_provider_subject == mapping.current_subject, f'Current subject mismatch for {mapping.employee_number}')
        require(mapping.clerk_user_id not in by_subject, f'Clerk user already linked: {mapping.employee_number}')
        changes.append((employee, mapping))
    if apply:
        for employee, mapping in changes:
            employee.identity_provider_subject = mapping.clerk_user_id
            audit(db, None, 'CLERK_IDENTITY_LINKED', 'employee', employee.id,
                  previous_subject=mapping.current_subject, clerk_user_id=mapping.clerk_user_id)
        db.flush()
    return [employee.employee_number for employee, _ in changes]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Apply the verified mapping in one transaction')
    args = parser.parse_args()
    mappings = [IdentityLink.model_validate(row) for row in json.loads(args.mapping.read_text())]
    with SessionLocal.begin() as db:
        changed = migrate_identities(db, mappings, apply=args.apply)
    print(f'{"Applied" if args.apply else "Dry run"}: {len(changed)} employee identity links. No balances or roles changed.')
