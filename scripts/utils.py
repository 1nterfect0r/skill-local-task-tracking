import datetime


def now_utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
