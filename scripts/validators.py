import re
import datetime
from errors import ValidationError

ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}


def validate_id(value: str, field_name: str = "id"):
    if not value or not ID_RE.fullmatch(value):
        raise ValidationError(f"Invalid {field_name}", {field_name: value})


def validate_status(value: str):
    validate_id(value, "status")


def validate_statuses(statuses):
    if not statuses or not isinstance(statuses, list):
        raise ValidationError("Statuses must be a non-empty list")
    seen = set()
    for s in statuses:
        validate_status(s)
        if s in seen:
            raise ValidationError("Duplicate status", {"status": s})
        seen.add(s)


def validate_tags(tags):
    if tags is None:
        return
    if not isinstance(tags, list):
        raise ValidationError("Tags must be a list")
    for t in tags:
        if not isinstance(t, str) or not t.strip():
            raise ValidationError("Tag must be a non-empty string")


def validate_priority(priority):
    if priority is None:
        return
    if priority not in ALLOWED_PRIORITIES:
        raise ValidationError("Invalid priority", {"priority": priority})


def _parse_iso(date_str: str):
    if date_str is None:
        return None
    s = date_str
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.date.fromisoformat(s)
        except ValueError:
            raise ValidationError("Invalid ISO 8601 date/datetime", {"due_date": date_str})


def parse_due_date(due_date):
    if due_date is None:
        return None
    val = _parse_iso(due_date)
    # normalize date to datetime at midnight UTC for sorting
    if isinstance(val, datetime.date) and not isinstance(val, datetime.datetime):
        return datetime.datetime.combine(val, datetime.time.min, tzinfo=datetime.timezone.utc)
    if isinstance(val, datetime.datetime) and val.tzinfo is None:
        return val.replace(tzinfo=datetime.timezone.utc)
    return val


def validate_due_date(due_date):
    if due_date is None:
        return
    _parse_iso(due_date)
