from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.core.errors import require
from app.models.entities import AuditLog, EmailDelivery, Notification, User


def local_today(user):
    return datetime.now(ZoneInfo(user.timezone)).date()


def lock_employee(db, employee_id):
    employee = db.scalar(select(User).where(User.id == employee_id).with_for_update().execution_options(populate_existing=True))
    require(employee is not None, 'Employee not found', 'not_found', 404)
    return employee


def lock_all_employees(db):
    return list(db.scalars(select(User).order_by(User.id).with_for_update()))


def audit(db, actor, action, entity, entity_id, **details):
    db.add(AuditLog(actor_id=actor.id if actor else None, action=action, entity_type=entity, entity_id=entity_id, details=details))


def notify(db, user_id, event, request_id):
    if not user_id:
        return
    employee = db.get(User, user_id)
    if not employee or employee.status != 'ACTIVE':
        return
    notification = Notification(user_id=user_id, type=event, message=f'Request #{request_id}: {event.lower().replace("_", " ")}.', request_id=request_id)
    db.add(notification)
    db.flush()
    if employee.email_notifications:
        db.add(EmailDelivery(notification_id=notification.id))
