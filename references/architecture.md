# Architecture: Integrity, Recovery, Journaling (v1)

## Table of contents
- [1) Data layout and responsibilities](#1-data-layout-and-responsibilities)
- [2) Locking model](#2-locking-model)
- [3) Move journaling and recovery](#3-move-journaling-and-recovery)
- [4) `integrity-check`: Process and data model](#4-integrity-check-process-and-data-model)
- [5) Meaning of `--fix` (conservative repairs)](#5-meaning-of---fix-conservative-repairs)
- [6) Duplicate resolution (rule + fallback)](#6-duplicate-resolution-rule--fallback)
- [7) Return fields (`ok`, `recovered`, `fixed`, `issues`, `found`)](#7-return-fields-ok-recovered-fixed-issues-found)

## 1) Data layout and responsibilities

Per project:
- `<project>/<status>/index.json` (Task metadata by status)
- `<project>/<status>/<task_id>.md` (Body file)
- `<project>/.lock` (exclusive project lock)
- `<project>/.tx_move.json` (move transaction journal)

Modules:
- `service.py`: Domain logic, integrity check, recovery.
- `storage.py`: atomic writes, locking, root protection.
- `validators.py`: Input/schema validation.

---

## 2) Locking model

`ProjectLock` uses an exclusive lock file (`O_CREAT|O_EXCL`).

- Activate Lock → `CONFLICT` (Exit 4), `details.reason = "LOCKED"`.
- Stale Lock (PID no longer active) is removed and reapplied with best effort.
- If stale recovery fails, it remains at `CONFLICT`.

Essential: mutating operations run under a lock; this prevents competing writers.

---

## 3) Move journaling and recovery

## 3.1 Journal file
Before a `move` the service writes `.tx_move.json`:
- `op: "move"`
- `task_id`
- `from`
- `to`
- `updated_meta` (planned target metadata)

## 3.2 Why Journal?
In the event of a crash/abort between body move and index update, a partial state could arise.
The journal makes this state deterministically recoverable.

## 3.3 Recovery trigger
Recovery runs when `.tx_move.json` exists:
- before integrity operations,
- via `integrity-check`,
- as well as in other workflows that ensure integrity.

## 3.4 Recovery logic (simplified)
1. Validate journal (`op`, fields, IDs/status).
2. Check source/destination index and body existence.
3. Recognize consistent end states:
   - already complete source **or** complete target → delete journal.
4. Repair inconsistent intermediate states:
   - if body already in target: clean source index, finalize target index.
   - if body is still in source: move body, finalize indices.
5. If the state is not resolvable: `INTEGRITY_ERROR`.

---

## 4) `integrity-check`: Process and data model

## 4.1 Process (without `--fix`)
1. Load project status directories.
2. Read indices per status.
3. Collect findings (`found`).
4. Include unresolved findings in `issues`.
5. `ok = (len(issues) == 0)`.

## 4.2 Process (with `--fix`)
In addition to above:
- carry out conservative repairs,
- log repair actions in `fixed`,
- leave remaining problems in `issues`.

## 4.3 Internal check classes (from code)
Typical `found`/`issues` types:
- `INDEX_ERROR`
- `DUPLICATE_TASK`
- `STATUS_DIR_MISSING`
- `META_NOT_OBJECT`
- `TASK_ID_MISMATCH`
- `STATUS_MISMATCH`
- `MISSING_FIELD`
- `MISSING_BODY`
- `ORPHAN_BODY`
- `STATUS_DIR_LIST_ERROR`

---

## 5) Meaning of `--fix` (conservative repairs)

`--fix` only repairs clearly deducible, low-risk cases:

1. **Missing index file** (`INDEX_ERROR` + missing file)
   - creates empty index.
   - `fixed`: `INDEX_CREATED`.

2. **Meta is not an object** (`META_NOT_OBJECT`)
   - replaced by minimal meta (`task_id`, `status`, `created_at`, `updated_at`).
   - `fixed`: `META_REPLACED`.

3. **Required fields are missing** (`MISSING_FIELD`)
   - adds missing fields:
     - `task_id` = index key,
     - `status` = status folder,
     - `created_at`/`updated_at` = `now`.
   - `fixed`: `FIELD_FILLED`.

4. **`meta.task_id` or `meta.status` inconsistent**
   - corrected to canonical values.
   - `fixed`: `TASK_ID_FIXED`, `STATUS_FIXED`.

5. **Empty/missing body file** (`MISSING_BODY`)
   - produces empty `<task_id>.md`.
   - `fixed`: `BODY_CREATED`.

6. **Orphan Body** (`ORPHAN_BODY`)
   - creates index entry only if `task_id` does not already exist in another status.
   - `fixed`: `ORPHAN_INDEX_CREATED`.

7. **Duplicates across statuses** (`DUPLICATE_TASK`)
   - selects a winner (see section 6), removes other index entries.
   - `fixed`: `DUPLICATE_RESOLVED`.
   - if the winner body is missing and a loose duplicate body exists:
     - Body is moved to the winner.
     - `fixed`: `BODY_MOVED_FROM_DUPLICATE`.

Cases that cannot be clearly remedied remain in `issues`.

---

## 6) Duplicate resolution (rule + fallback)

If a `task_id` occurs in multiple status indices:

1. Primary rule: **newest `updated_at` wins**.
2. If no parseable `updated_at` is available:
   - Fallback: **Project status order** (lexicographically sorted status names; first hit wins).
3. Last fallback: first status mapping found.

These rules are deterministic and reproducible.

---

## 7) Return fields (`ok`, `recovered`, `fixed`, `issues`, `found`)

`integrity-check` always returns:

```json
{
  "ok": false,
  "project_id": "acme-s4",
  "recovered": true,
  "fixed": [],
  "issues": [],
  "found": []
}
```

Semantics:
- `found`: all problems found (regardless of whether fixed).
- `fixed`: only repairs actually carried out.
- `issues`: remaining open issues after optional fix.
- `recovered`: `true` if move-journal recovery was performed in this run.
- `ok`: if and only if `issues` is empty; otherwise `false`.
