from datetime import datetime, timezone
from typing import Optional


def to_utc_naive(value: Optional[datetime]) -> Optional[datetime]:
    """
    Normalize a datetime to naive UTC.

    All scheduling logic works in UTC. Naive input is assumed to already be UTC;
    aware input (and aware values read back from PostgreSQL) is converted.
    """
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
