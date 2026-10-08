from datetime import date, timedelta
from decimal import Decimal


def working_days(start: date, end: date, weekdays: list[int], holidays: set[date], portion='FULL'):
    """Pure, deterministic date calculation. ISO weekday convention: Monday=0."""
    fraction = Decimal('1') if portion == 'FULL' else Decimal('0.5')
    return [(start + timedelta(days=n), fraction, portion) for n in range((end - start).days + 1)
            if (start + timedelta(days=n)).weekday() in weekdays and start + timedelta(days=n) not in holidays]


def overlaps(a: str, b: str) -> bool:
    return a == 'FULL' or b == 'FULL' or a == b
