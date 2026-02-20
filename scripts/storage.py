import json
import os
import tempfile
from errors import ValidationError, ConflictError, IntegrityError, NotFoundError

ROOT_ENV = "TASK_TRACKING_ROOT"
DEFAULT_DIR = ".task_tracking"


def _validate_root_env_value(root_value):
    # Guard against parent traversal segments in configured root values.
    # We reject both POSIX and Windows-style separators.
    normalized = root_value.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise ValidationError(
            "TASK_TRACKING_ROOT must not contain '..' path segments",
            {"env": ROOT_ENV, "value": root_value},
        )


def get_root():
    root = os.getenv(ROOT_ENV)
    if not root:
        root = os.path.join(os.getcwd(), DEFAULT_DIR)
    else:
        _validate_root_env_value(root)
    return os.path.abspath(root)


def safe_join(root, *parts):
    root_real = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(root, *parts))
    try:
        if os.path.commonpath([root_real, candidate]) != root_real:
            raise ValidationError("Path escapes root", {"path": candidate})
    except ValueError:
        # e.g. different drives on Windows
        raise ValidationError("Path escapes root", {"path": candidate})
    return candidate


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise IntegrityError("Missing required file", {"path": path})
    except json.JSONDecodeError:
        raise IntegrityError("Invalid JSON", {"path": path})


def _fsync_dir(directory):
    try:
        dir_fd = os.open(directory, getattr(os, "O_DIRECTORY", 0))
    except Exception:
        return
    try:
        os.fsync(dir_fd)
    except Exception:
        pass
    finally:
        try:
            os.close(dir_fd)
        except Exception:
            pass


def write_json_atomic(path, data):
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, sort_keys=True)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, path)
        _fsync_dir(directory)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def write_text_atomic(path, text):
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text or "")
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, path)
        _fsync_dir(directory)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _pid_alive(pid):
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


class ProjectLock:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.lock_path = os.path.join(project_dir, ".lock")
        self.fd = None

    def __enter__(self):
        if not os.path.isdir(self.project_dir):
            raise NotFoundError("Project not found", {"path": self.project_dir})
        try:
            self.fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = json.dumps({"pid": os.getpid()})
            os.write(self.fd, payload.encode("utf-8"))
            return self
        except FileExistsError:
            # try to break stale lock if PID is not alive
            try:
                with open(self.lock_path, "r", encoding="utf-8") as f:
                    content = f.read().strip() or "{}"
                data = json.loads(content)
                pid = data.get("pid")
            except Exception:
                raise ConflictError("Project is locked", {"lock": self.lock_path, "reason": "LOCKED"})

            if pid is None or _pid_alive(pid):
                raise ConflictError("Project is locked", {"lock": self.lock_path, "reason": "LOCKED"})

            # stale lock: remove and acquire again
            try:
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
                self.fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                payload = json.dumps({"pid": os.getpid()})
                os.write(self.fd, payload.encode("utf-8"))
                return self
            except Exception:
                raise ConflictError("Project is locked", {"lock": self.lock_path, "reason": "LOCKED"})

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.fd is not None:
                os.close(self.fd)
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        finally:
            self.fd = None
