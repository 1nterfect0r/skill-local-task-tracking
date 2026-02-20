import os
import datetime
from errors import ValidationError, NotFoundError, ConflictError, IntegrityError
from storage import get_root, safe_join, read_json, write_json_atomic, write_text_atomic, ProjectLock
from validators import validate_id, validate_status, validate_statuses, validate_tags, validate_priority, validate_due_date, parse_due_date
from utils import now_utc_iso, task_id_from_title, title_from_task_id


def _project_dir(root, project_id):
    return safe_join(root, project_id)


# project.json is intentionally unused; statuses are always discovered from directories

def _status_dir(root, project_id, status):
    return safe_join(root, project_id, status)


def _index_path(root, project_id, status):
    return safe_join(root, project_id, status, "index.json")


def _body_path(root, project_id, status, task_id):
    return safe_join(root, project_id, status, f"{task_id}.md")


def _tx_path(root, project_id):
    return safe_join(root, project_id, ".tx_move.json")


def _meta_for_storage(meta):
    out = dict(meta or {})
    # title is derived from task_id and should not be persisted
    out.pop("title", None)
    return out


def _recover_move(root, project_id):
    tx_path = _tx_path(root, project_id)
    if not os.path.exists(tx_path):
        return
    tx = read_json(tx_path)
    if not isinstance(tx, dict) or tx.get("op") != "move":
        raise IntegrityError("Invalid transaction file", {"path": tx_path})

    task_id = tx.get("task_id")
    from_status = tx.get("from")
    to_status = tx.get("to")
    if not task_id or not from_status or not to_status:
        raise IntegrityError("Invalid transaction data", {"path": tx_path})

    validate_id(task_id, "task_id")
    validate_status(from_status)
    validate_status(to_status)

    # ensure statuses are part of the project definition
    statuses = load_project_statuses(root, project_id)
    if from_status not in statuses or to_status not in statuses:
        raise IntegrityError("Invalid transaction status", {"from": from_status, "to": to_status})

    src_body = _body_path(root, project_id, from_status, task_id)
    dst_body = _body_path(root, project_id, to_status, task_id)

    src_index = read_index(root, project_id, from_status)
    dst_index = read_index(root, project_id, to_status)

    in_src = task_id in src_index
    in_dst = task_id in dst_index
    src_body_exists = os.path.exists(src_body)
    dst_body_exists = os.path.exists(dst_body)

    # Consistent states
    if src_body_exists and in_src and not dst_body_exists and not in_dst:
        os.remove(tx_path)
        return
    if dst_body_exists and in_dst and not src_body_exists and not in_src:
        os.remove(tx_path)
        return
    if src_body_exists and dst_body_exists:
        raise IntegrityError("Task body exists in both statuses", {"task_id": task_id})
    if in_src and in_dst:
        raise IntegrityError("Task exists in multiple indexes", {"task_id": task_id})

    updated_meta = tx.get("updated_meta")
    if not isinstance(updated_meta, dict):
        base = dst_index.get(task_id) or src_index.get(task_id) or {}
        updated_meta = dict(base)

    updated_meta = _meta_for_storage(updated_meta)
    updated_meta["updated_at"] = now_utc_iso()

    # Commit to destination (deterministic recovery)
    if dst_body_exists:
        src_index.pop(task_id, None)
        dst_index[task_id] = updated_meta
        write_index(root, project_id, from_status, src_index)
        write_index(root, project_id, to_status, dst_index)
        os.remove(tx_path)
        return

    if src_body_exists:
        os.replace(src_body, dst_body)
        src_index.pop(task_id, None)
        dst_index[task_id] = updated_meta
        write_index(root, project_id, from_status, src_index)
        write_index(root, project_id, to_status, dst_index)
        os.remove(tx_path)
        return

    raise IntegrityError("Cannot recover move", {"task_id": task_id})


def _recover_if_needed(root, project_id):
    tx_path = _tx_path(root, project_id)
    if os.path.exists(tx_path):
        with ProjectLock(_project_dir(root, project_id)):
            _recover_move(root, project_id)


def _ensure_integrity(project_id, locked=False):
    """Run integrity-check --fix before operations; abort if issues remain."""
    result = integrity_check(project_id, fix=True, locked=locked)
    if result.get("ok"):
        return

    raise IntegrityError(
        "Integrity check failed",
        {
            "project_id": project_id,
            "issues": result.get("issues", []),
            "fixed": result.get("fixed", []),
            "found": result.get("found", []),
            "recovered": result.get("recovered", False),
        },
    )


def load_project_statuses(root, project_id):
    project_dir = _project_dir(root, project_id)
    if not os.path.isdir(project_dir):
        raise NotFoundError("Project not found", {"project_id": project_id})
    # Always discover status dirs (include dirs even if index.json is missing)
    statuses = []
    for entry in os.listdir(project_dir):
        path = os.path.join(project_dir, entry)
        if not os.path.isdir(path):
            continue
        try:
            validate_status(entry)
        except ValidationError:
            continue
        statuses.append(entry)
    statuses = sorted(statuses)
    if not statuses:
        raise IntegrityError("No statuses found", {"project_id": project_id})
    validate_statuses(statuses)
    return statuses


def read_index(root, project_id, status):
    index_path = _index_path(root, project_id, status)
    data = read_json(index_path)
    if not isinstance(data, dict):
        raise IntegrityError("Index must be a JSON object", {"status": status})
    return data


def write_index(root, project_id, status, data):
    index_path = _index_path(root, project_id, status)
    write_json_atomic(index_path, data)


def find_task(root, project_id, task_id):
    statuses = load_project_statuses(root, project_id)
    found = []
    for status in statuses:
        index = read_index(root, project_id, status)
        if task_id in index:
            found.append((status, index[task_id]))
    if not found:
        raise NotFoundError("Task not found", {"project_id": project_id, "task_id": task_id})
    if len(found) > 1:
        raise IntegrityError("Task exists in multiple statuses", {"project_id": project_id, "task_id": task_id})
    return found[0]


def task_exists_anywhere(root, project_id, task_id):
    statuses = load_project_statuses(root, project_id)
    for status in statuses:
        index = read_index(root, project_id, status)
        if task_id in index:
            return True
    return False


def init_project(project_id, statuses):
    validate_id(project_id, "project_id")
    validate_statuses(statuses)
    root = get_root()
    project_dir = _project_dir(root, project_id)
    if os.path.exists(project_dir):
        raise ConflictError("Project already exists", {"project_id": project_id})
    os.makedirs(project_dir, exist_ok=False)
    for status in statuses:
        status_dir = _status_dir(root, project_id, status)
        os.makedirs(status_dir, exist_ok=True)
        write_json_atomic(_index_path(root, project_id, status), {})
    return {"ok": True, "project_id": project_id, "statuses": statuses}


def add_task(project_id, title, status, task_id=None, body=None, tags=None, assignee=None, priority=None, due_date=None):
    validate_id(project_id, "project_id")
    if not title or not isinstance(title, str):
        raise ValidationError("Title is required")
    normalized_title = " ".join(title.strip().split())
    if not normalized_title:
        raise ValidationError("Title is required")
    derived_task_id = task_id_from_title(normalized_title)
    if not derived_task_id:
        raise ValidationError("Title is required")
    validate_id(derived_task_id, "task_id")
    if title_from_task_id(derived_task_id) != normalized_title:
        raise ValidationError("Title must use spaces instead of underscores", {"title": title})
    root = get_root()

    tags_list = None
    if tags is not None:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]
        validate_tags(tags_list)

    if assignee is not None and not isinstance(assignee, str):
        raise ValidationError("Assignee must be a string")

    validate_priority(priority)
    validate_due_date(due_date)

    with ProjectLock(_project_dir(root, project_id)):
        _ensure_integrity(project_id, locked=True)

        statuses = load_project_statuses(root, project_id)
        if status is None:
            status = statuses[0]
        validate_status(status)
        if status not in statuses:
            raise ValidationError("Invalid status", {"status": status})

        indexes = {}
        all_ids = set()
        for st in statuses:
            idx = read_index(root, project_id, st)
            indexes[st] = idx
            all_ids.update(idx.keys())

        if task_id:
            validate_id(task_id, "task_id")
            if task_id != derived_task_id:
                raise ValidationError("Title and task_id must match", {"title": normalized_title, "task_id": task_id})
            if task_id in all_ids:
                raise ConflictError("Task ID already exists", {"task_id": task_id})
        else:
            base = derived_task_id
            task_id = base
            suffix = 2
            while task_id in all_ids:
                task_id = f"{base}-{suffix}"
                suffix += 1

        index = indexes[status]
        if task_id in index:
            raise ConflictError("Task ID already exists", {"task_id": task_id})

        body_path = _body_path(root, project_id, status, task_id)
        if os.path.exists(body_path):
            raise IntegrityError("Body file exists without index", {"task_id": task_id, "status": status})

        now = now_utc_iso()
        meta = {
            "task_id": task_id,
            "created_at": now,
            "updated_at": now,
        }
        if tags_list is not None:
            meta["tags"] = tags_list
        if assignee is not None:
            meta["assignee"] = assignee
        if priority is not None:
            meta["priority"] = priority
        if due_date is not None:
            meta["due_date"] = due_date

        try:
            write_text_atomic(body_path, body or "")
            index_new = dict(index)
            index_new[task_id] = meta
            write_index(root, project_id, status, index_new)
        except Exception:
            try:
                if os.path.exists(body_path):
                    os.remove(body_path)
            except Exception:
                pass
            raise

    return {
        "ok": True,
        "project_id": project_id,
        "task_id": task_id,
        "status": status,
        "title": title_from_task_id(task_id),
    }

def list_tasks(project_id, status=None, tag=None, assignee=None, priority=None, fields=None, limit=100, offset=0, sort="updated_at", desc=True):
    validate_id(project_id, "project_id")
    root = get_root()
    with ProjectLock(_project_dir(root, project_id)):
        _ensure_integrity(project_id, locked=True)
        statuses = load_project_statuses(root, project_id)
        if status:
            validate_status(status)
            if status not in statuses:
                raise NotFoundError("Status not found", {"status": status})
            statuses = [status]

        if limit is None or limit <= 0:
            raise ValidationError("Limit must be > 0")
        if limit > 1000:
            raise ValidationError("Limit must be <= 1000")
        if offset is None or offset < 0:
            raise ValidationError("Offset must be >= 0")

        allowed_sort = {"created_at", "updated_at", "title", "priority", "due_date"}
        if sort not in allowed_sort:
            raise ValidationError("Invalid sort field", {"sort": sort})

        items = []
        for st in statuses:
            index = read_index(root, project_id, st)
            for _, meta in index.items():
                if not isinstance(meta, dict):
                    continue
                meta_out = dict(meta)
                meta_out["status"] = st
                meta_out["title"] = title_from_task_id(meta_out.get("task_id") or "")
                if tag and ("tags" not in meta_out or tag not in meta_out.get("tags", [])):
                    continue
                if assignee and meta_out.get("assignee") != assignee:
                    continue
                if priority and meta_out.get("priority") != priority:
                    continue
                items.append(meta_out)

    def sort_val(m):
        val = m.get(sort)
        if sort == "due_date":
            if val is None:
                return None
            try:
                return parse_due_date(val)
            except ValidationError:
                return None
        return val

    # sort with missing values last (missing sorted by task_id for stability)
    present = [m for m in items if sort_val(m) is not None]
    missing = [m for m in items if sort_val(m) is None]

    def key_fn(m):
        return (sort_val(m), m.get("task_id"))

    present_sorted = sorted(present, key=key_fn, reverse=bool(desc))
    missing_sorted = sorted(missing, key=lambda m: m.get("task_id"))
    items_sorted = present_sorted + missing_sorted

    paged = items_sorted[offset: offset + limit]

    if fields:
        fields_set = [f.strip() for f in fields.split(",") if f.strip()]
    else:
        fields_set = ["task_id", "status", "title", "priority", "updated_at"]

    # ensure task_id + status are always present
    for required in ("task_id", "status"):
        if required not in fields_set:
            fields_set.append(required)

    out_items = []
    for m in paged:
        item = {}
        for f in fields_set:
            item[f] = m.get(f)
        out_items.append(item)

    return {"ok": True, "project_id": project_id, "count": len(out_items), "items": out_items}

def show_task(project_id, task_id, include_body=False, max_body_chars=None, max_body_lines=None):
    validate_id(project_id, "project_id")
    validate_id(task_id, "task_id")
    if max_body_chars is not None and max_body_chars < 0:
        raise ValidationError("max_body_chars must be >= 0")
    if max_body_lines is not None and max_body_lines < 0:
        raise ValidationError("max_body_lines must be >= 0")
    root = get_root()
    with ProjectLock(_project_dir(root, project_id)):
        _ensure_integrity(project_id, locked=True)
        status, meta = find_task(root, project_id, task_id)
        meta_out = dict(meta)
        meta_out["title"] = title_from_task_id(task_id)
        result = {"ok": True, "project_id": project_id, "task_id": task_id, "status": status, "meta": meta_out}

        if include_body:
            body_path = _body_path(root, project_id, status, task_id)
            try:
                with open(body_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except FileNotFoundError:
                raise IntegrityError("Body file missing", {"task_id": task_id})

            truncated = False
            if max_body_lines is not None:
                lines = text.splitlines(keepends=True)
                if len(lines) > max_body_lines:
                    text = "".join(lines[:max_body_lines])
                    truncated = True
            if max_body_chars is not None and len(text) > max_body_chars:
                text = text[:max_body_chars]
                truncated = True

            body_obj = {"text": text, "truncated": truncated}
            if max_body_chars is not None:
                body_obj["max_body_chars"] = max_body_chars
            if max_body_lines is not None:
                body_obj["max_body_lines"] = max_body_lines
            result["body"] = body_obj

    return result

def move_task(project_id, task_id, new_status):
    validate_id(project_id, "project_id")
    validate_id(task_id, "task_id")
    validate_status(new_status)
    root = get_root()

    with ProjectLock(_project_dir(root, project_id)):
        _ensure_integrity(project_id, locked=True)

        statuses = load_project_statuses(root, project_id)
        if new_status not in statuses:
            raise ValidationError("Invalid status", {"status": new_status})

        current_status, meta = find_task(root, project_id, task_id)
        if current_status == new_status:
            raise ValidationError("Task already in target status", {"status": new_status})

        src_index = read_index(root, project_id, current_status)
        dst_index = read_index(root, project_id, new_status)

        if task_id not in src_index:
            raise IntegrityError("Task missing from source index", {"task_id": task_id})
        if task_id in dst_index:
            raise IntegrityError("Task already exists in destination index", {"task_id": task_id})

        updated = _meta_for_storage(meta)
        updated["updated_at"] = now_utc_iso()

        src_new = dict(src_index)
        dst_new = dict(dst_index)
        src_new.pop(task_id, None)
        dst_new[task_id] = updated

        src_body = _body_path(root, project_id, current_status, task_id)
        dst_body = _body_path(root, project_id, new_status, task_id)

        if not os.path.exists(src_body):
            raise IntegrityError("Body file missing", {"task_id": task_id})

        tx_path = _tx_path(root, project_id)
        write_json_atomic(tx_path, {
            "op": "move",
            "task_id": task_id,
            "from": current_status,
            "to": new_status,
            "updated_meta": updated,
        })

        # perform move + index updates with best-effort rollback
        try:
            os.replace(src_body, dst_body)
            write_index(root, project_id, current_status, src_new)
            write_index(root, project_id, new_status, dst_new)
            try:
                if os.path.exists(tx_path):
                    os.remove(tx_path)
            except Exception:
                pass
        except Exception as e:
            # rollback attempt
            try:
                if os.path.exists(dst_body) and not os.path.exists(src_body):
                    os.replace(dst_body, src_body)
            except Exception:
                pass
            # restore old indexes best-effort
            try:
                write_index(root, project_id, current_status, src_index)
                write_index(root, project_id, new_status, dst_index)
            except Exception:
                pass
            raise IntegrityError("Atomic move failed", {"error": str(e)})

    return {
        "ok": True,
        "project_id": project_id,
        "task_id": task_id,
        "from": current_status,
        "to": new_status,
        "updated_at": updated["updated_at"],
    }

def meta_update(project_id, task_id, patch):
    validate_id(project_id, "project_id")
    validate_id(task_id, "task_id")
    if not isinstance(patch, dict):
        raise ValidationError("Patch must be a JSON object")
    if "set" in patch:
        set_obj = patch.get("set")
        if not isinstance(set_obj, dict):
            raise ValidationError("Invalid patch format", {"field": "set"})
    else:
        set_obj = {}
    if "unset" in patch:
        unset_list = patch.get("unset")
        if not isinstance(unset_list, list):
            raise ValidationError("Invalid patch format", {"field": "unset"})
    else:
        unset_list = []

    forbidden = {"task_id", "created_at", "updated_at", "status", "title"}
    for k in set_obj.keys():
        if k in forbidden:
            raise ValidationError("Forbidden field in set", {"field": k})
    for k in unset_list:
        if not isinstance(k, str) or not k:
            raise ValidationError("Invalid patch format", {"field": "unset"})
        if k in forbidden:
            raise ValidationError("Forbidden field in unset", {"field": k})

    # title is derived from task_id; not stored or updated
    if "tags" in set_obj:
        if set_obj.get("tags") is None:
            raise ValidationError("Tags must be a list")
        validate_tags(set_obj.get("tags"))
    if "assignee" in set_obj:
        if not isinstance(set_obj.get("assignee"), str):
            raise ValidationError("Assignee must be a string")
    if "priority" in set_obj:
        if set_obj.get("priority") is None:
            raise ValidationError("Invalid priority", {"priority": None})
        validate_priority(set_obj.get("priority"))
    if "due_date" in set_obj:
        if set_obj.get("due_date") is None or not isinstance(set_obj.get("due_date"), str):
            raise ValidationError("Invalid ISO 8601 date/datetime", {"due_date": set_obj.get("due_date")})
        validate_due_date(set_obj.get("due_date"))

    root = get_root()
    with ProjectLock(_project_dir(root, project_id)):
        _ensure_integrity(project_id, locked=True)
        status, meta = find_task(root, project_id, task_id)
        index = read_index(root, project_id, status)
        if task_id not in index:
            raise IntegrityError("Task missing from index", {"task_id": task_id})

        updated = _meta_for_storage(meta)
        for k, v in set_obj.items():
            updated[k] = v
        for k in unset_list:
            if k in updated:
                updated.pop(k, None)

        updated["updated_at"] = now_utc_iso()
        index[task_id] = updated
        write_index(root, project_id, status, index)

    return {
        "ok": True,
        "project_id": project_id,
        "task_id": task_id,
        "updated_at": updated["updated_at"],
        "changed": {"set": sorted(set_obj.keys()), "unset": sorted(unset_list)},
    }

def set_body(project_id, task_id, text=None, file_path=None):
    validate_id(project_id, "project_id")
    validate_id(task_id, "task_id")
    if (text is None and file_path is None) or (text is not None and file_path is not None):
        raise ValidationError("Provide exactly one of --text or --file")
    root = get_root()

    if file_path is not None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            raise NotFoundError("Input file not found", {"file": file_path})

    with ProjectLock(_project_dir(root, project_id)):
        _ensure_integrity(project_id, locked=True)
        status, meta = find_task(root, project_id, task_id)
        index = read_index(root, project_id, status)
        if task_id not in index:
            raise IntegrityError("Task missing from index", {"task_id": task_id})
        body_path = _body_path(root, project_id, status, task_id)
        write_text_atomic(body_path, text or "")
        meta_updated = _meta_for_storage(meta)
        meta_updated["updated_at"] = now_utc_iso()
        index[task_id] = meta_updated
        write_index(root, project_id, status, index)

    return {
        "ok": True,
        "project_id": project_id,
        "task_id": task_id,
        "updated_at": meta_updated["updated_at"],
    }

def integrity_check(project_id, fix=False, locked=False):
    validate_id(project_id, "project_id")
    root = get_root()
    recovered = False

    def _minimal_meta(task_id):
        now = now_utc_iso()
        return {
            "task_id": task_id,
            "created_at": now,
            "updated_at": now,
        }

    def _parse_updated(meta):
        if not isinstance(meta, dict):
            return None
        val = meta.get("updated_at")
        if not val or not isinstance(val, str):
            return None
        s = val
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.datetime.fromisoformat(s)
        except Exception:
            return None

    def _pick_winner(task_id, statuses, index_map, project_statuses):
        candidates = []
        for st in statuses:
            meta = index_map.get(st, {}).get(task_id, {})
            dt = _parse_updated(meta)
            candidates.append((dt, st))
        with_dates = [c for c in candidates if c[0] is not None]
        if with_dates:
            return max(with_dates, key=lambda x: x[0])[1], "updated_at"
        for st in project_statuses:
            if st in statuses:
                return st, "status_order"
        return statuses[0], "status_order"

    def _run_check():
        project_statuses = load_project_statuses(root, project_id)
        found = []
        issues = []
        fixed = []
        required_fields = ["task_id", "created_at", "updated_at"]

        index_map = {}
        id_to_statuses = {}
        index_changed_statuses = set()
        index_error_statuses = set()

        def _record(issue, resolved=False, fixed_item=None):
            found.append(issue)
            if resolved:
                if fixed_item is not None:
                    fixed.append(fixed_item)
            else:
                issues.append(issue)

        for status in project_statuses:
            status_dir = _status_dir(root, project_id, status)
            try:
                index = read_index(root, project_id, status)
            except IntegrityError as e:
                issue = {"type": "INDEX_ERROR", "status": status, "message": e.message}
                # fix missing index file conservatively
                if fix and e.message == "Missing required file" and os.path.isdir(status_dir):
                    index = {}
                    index_map[status] = index
                    index_changed_statuses.add(status)
                    _record(issue, resolved=True, fixed_item={"type": "INDEX_CREATED", "status": status})
                else:
                    _record(issue)
                    index_error_statuses.add(status)
                    continue
            index_map[status] = index
            for tid in index.keys():
                id_to_statuses.setdefault(tid, []).append(status)

        # resolve duplicates (keep newest updated_at)
        for task_id, sts in list(id_to_statuses.items()):
            if len(sts) <= 1:
                continue
            issue = {"type": "DUPLICATE_TASK", "task_id": task_id, "statuses": sts}
            if not fix:
                _record(issue)
                continue

            _record(issue, resolved=True)
            winner, rule = _pick_winner(task_id, sts, index_map, project_statuses)
            removed = []
            for st in sts:
                if st == winner:
                    continue
                if task_id in index_map.get(st, {}):
                    index_map[st].pop(task_id, None)
                    index_changed_statuses.add(st)
                    removed.append(st)

            id_to_statuses[task_id] = [winner]
            if removed:
                fixed.append({"type": "DUPLICATE_RESOLVED", "task_id": task_id, "kept": winner, "removed": removed, "rule": rule})

            # if winner has no body but another status does, move one body to winner
            winner_body = _body_path(root, project_id, winner, task_id)
            if not os.path.exists(winner_body):
                for st in sts:
                    if st == winner:
                        continue
                    candidate_body = _body_path(root, project_id, st, task_id)
                    if os.path.exists(candidate_body):
                        os.replace(candidate_body, winner_body)
                        fixed.append({"type": "BODY_MOVED_FROM_DUPLICATE", "task_id": task_id, "from": st, "to": winner})
                        break

        for status in project_statuses:
            status_dir = _status_dir(root, project_id, status)
            if not os.path.isdir(status_dir):
                issue = {"type": "STATUS_DIR_MISSING", "status": status, "path": status_dir}
                _record(issue)
                continue
            if status in index_error_statuses:
                continue

            index = index_map.get(status, {})
            index_changed = status in index_changed_statuses

            for task_id, meta in list(index.items()):
                if not isinstance(meta, dict):
                    issue = {"type": "META_NOT_OBJECT", "status": status, "task_id": task_id}
                    if fix:
                        index[task_id] = _minimal_meta(task_id)
                        index_changed = True
                        _record(issue, resolved=True, fixed_item={"type": "META_REPLACED", "status": status, "task_id": task_id})
                    else:
                        _record(issue)
                    continue

                # mismatches
                if meta.get("task_id") != task_id:
                    issue = {"type": "TASK_ID_MISMATCH", "status": status, "task_id": task_id}
                    if fix:
                        meta["task_id"] = task_id
                        index_changed = True
                        _record(issue, resolved=True, fixed_item={"type": "TASK_ID_FIXED", "status": status, "task_id": task_id})
                    else:
                        _record(issue)

                for f in required_fields:
                    if f not in meta:
                        issue = {"type": "MISSING_FIELD", "status": status, "task_id": task_id, "field": f}
                        if fix:
                            if f == "task_id":
                                meta["task_id"] = task_id
                            else:
                                meta[f] = now_utc_iso()
                            index_changed = True
                            _record(issue, resolved=True, fixed_item={"type": "FIELD_FILLED", "status": status, "task_id": task_id, "field": f})
                        else:
                            _record(issue)

                body_path = _body_path(root, project_id, status, task_id)
                if not os.path.exists(body_path):
                    issue = {"type": "MISSING_BODY", "status": status, "task_id": task_id, "path": body_path}
                    if fix:
                        write_text_atomic(body_path, "")
                        _record(issue, resolved=True, fixed_item={"type": "BODY_CREATED", "status": status, "task_id": task_id, "path": body_path})
                    else:
                        _record(issue)

            # extra body files without index entry
            try:
                for name in os.listdir(status_dir):
                    if not name.endswith(".md"):
                        continue
                    tid = name[:-3]
                    if tid not in index:
                        issue = {"type": "ORPHAN_BODY", "status": status, "task_id": tid, "path": os.path.join(status_dir, name)}
                        if fix:
                            # only auto-add if task_id not present elsewhere
                            if tid not in id_to_statuses:
                                index[tid] = _minimal_meta(tid)
                                index_changed = True
                                id_to_statuses.setdefault(tid, []).append(status)
                                _record(issue, resolved=True, fixed_item={"type": "ORPHAN_INDEX_CREATED", "status": status, "task_id": tid})
                            else:
                                _record(issue)
                        else:
                            _record(issue)
            except Exception:
                issue = {"type": "STATUS_DIR_LIST_ERROR", "status": status, "path": status_dir}
                _record(issue)

            if fix and index_changed:
                write_index(root, project_id, status, index)

        return found, issues, fixed

    if os.path.exists(_tx_path(root, project_id)):
        if locked:
            _recover_move(root, project_id)
        else:
            with ProjectLock(_project_dir(root, project_id)):
                _recover_move(root, project_id)
        recovered = True

    if fix:
        if locked:
            found, issues, fixed = _run_check()
        else:
            with ProjectLock(_project_dir(root, project_id)):
                found, issues, fixed = _run_check()
    else:
        found, issues, fixed = _run_check()

    return {
        "ok": len(issues) == 0,
        "project_id": project_id,
        "recovered": recovered,
        "fixed": fixed,
        "issues": issues,
        "found": found,
    }
