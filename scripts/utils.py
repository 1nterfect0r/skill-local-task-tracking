import datetime
import re
import unicodedata


def now_utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def slugify(text: str) -> str:
    if text is None:
        return "task"
    norm = unicodedata.normalize("NFKD", text)
    ascii_text = norm.encode("ascii", "ignore").decode("ascii")
    s = ascii_text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "task"


def task_id_from_title(title: str) -> str:
    if title is None:
        return ""
    normalized = " ".join(title.strip().split())
    return normalized.replace(" ", "_")


def title_from_task_id(task_id: str) -> str:
    if task_id is None:
        return ""
    return task_id.replace("_", " ")
