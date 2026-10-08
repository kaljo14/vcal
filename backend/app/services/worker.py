"""Transactional outbox consumer: python -m app.services.worker."""
import logging
import smtplib
import ssl
import time
from datetime import timedelta
from email.message import EmailMessage
from sqlalchemy import select
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.entities import EmailDelivery, Notification, User, utcnow

logger = logging.getLogger('workleave.worker')


def deliver_one():
    config = settings()
    if not config.smtp_host:
        return False
    with SessionLocal.begin() as db:
        delivery = db.scalar(select(EmailDelivery).where(EmailDelivery.status.in_(['PENDING', 'RETRY']), EmailDelivery.next_attempt_at <= utcnow()).order_by(EmailDelivery.id).with_for_update(skip_locked=True).limit(1))
        if not delivery:
            return False
        notification = db.get(Notification, delivery.notification_id)
        employee = db.get(User, notification.user_id)
        if not employee.email_notifications or employee.status != 'ACTIVE':
            delivery.status = 'SKIPPED'
            return True
        message = EmailMessage()
        message['From'], message['To'] = config.smtp_from, employee.email
        message['Subject'] = 'Workleave request update'
        message['Message-ID'] = f'<workleave-{delivery.id}@{config.smtp_from.split("@")[-1]}>'
        message.set_content(notification.message + '\nOpen Workleave to review the details.')
        delivery.attempts += 1
        try:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as smtp:
                if config.smtp_starttls:
                    smtp.starttls(context=ssl.create_default_context())
                if config.smtp_user:
                    smtp.login(config.smtp_user, config.smtp_password)
                smtp.send_message(message)
            delivery.status, delivery.delivered_at = 'DELIVERED', utcnow()
        except (OSError, smtplib.SMTPException):
            delivery.status = 'FAILED' if delivery.attempts >= 10 else 'RETRY'
            delivery.next_attempt_at = utcnow() + timedelta(seconds=min(3600, 2 ** delivery.attempts * 30))
            logger.warning('Email delivery deferred; delivery_id=%s attempt=%s', delivery.id, delivery.attempts)
        return True


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            if not deliver_one():
                time.sleep(5)
        except Exception:
            logger.error('Outbox polling failed; retrying')
            time.sleep(10)
