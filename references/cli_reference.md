# CLI reference (normative, v1)

## Table of contents
- [1) Global Conventions](#1-global-conventions)
  - [1.0 Invocation forms and complete command set](#10-invocation-forms-and-complete-command-set)
- [2) Exit Codes and error.code](#2-exit-codes-and-errorcode)
- [3) Locking/conflict semantics](#3-lockingconflict-semantics)
- [4) Command reference](#4-command-reference)
  - [4.1 init-project](#41-init-project)
  - [4.2 add](#42-add)
  - [4.3 list](#43-list)
  - [4.4 show](#44-show)
  - [4.5 move](#45-move)
  - [4.6 meta-update](#46-meta-update)
  - [4.7 set-body](#47-set-body)
  - [4.8 integrity-check](#48-integrity-check)

## 1) Global conventions

### 1.0 Invocation forms and complete command set
Use these invocation form:

```bash
python3 {baseDir}/scripts/task_tracking.py <command> ...
```

Complete command set (CLI parity):
- `init-project`
- `add`
- `list`
- `show`
- `move`
- `meta-update`
- `set-body`
- `integrity-check`

### 1.1 Output format
- `stdout`: always exactly **one JSON object**.
- Errors are also JSON:

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "...",
    "details": {}
  }
}
```

### 1.2 Storage Root
- `TASK_TRACKING_ROOT` controls the root path.
- If not set: `${CWD}/.task_tracking`.
- If set: Path is resolved absolutely.
- `TASK_TRACKING_ROOT` must not contain a `..` segment (otherwise `VALIDATION_ERROR`, exit 2).

### 1.3 ID/Status Validation
- `project_id`, `task_id`, `status` follow Regex: `^[A-Za-z0-9_-]+$`.

### 1.4 Derived field (`status`)
- `status` is derived from the status folder and is not stored in task metadata.
- `task_id` is the single user-facing task identifier.

---

## 2) Exit codes and error.code

| Exit | error.code | Meaning |
|---:|---|---|
| 0 | *(no error object)* | Success |
| 2 | `VALIDATION_ERROR` | Invalid arguments/inputs/schema |
| 3 | `NOT_FOUND` | Project/task/file not found |
| 4 | `CONFLICT` | Conflict (e.g., active lock, duplicate id) |
| 5 | `INTEGRITY_ERROR` | Data inconsistency detected |
| 10 | `UNEXPECTED_ERROR` | Unclassified runtime error |

Note: Agents can robustly check for **both** (`exit_code` and `error.code`).

---

## 3) Locking/conflict semantics

### 3.1 Project Lock
Most project operations use an exclusive lock file `<project_dir>/.lock`.

- With active lock: `CONFLICT` (Exit 4) with details:

```json
{
  "lock": "/.../<project>/.lock",
  "reason": "LOCKED"
}
```

- Stale lock recovery: If PID from the lock file is no longer alive, the service tries to break the lock and take over again.

### 3.2 Lock behavior per command
- Always under project lock: `add`, `list`, `show`, `move`, `meta-update`, `set-body`.
- `integrity-check --fix`: under project lock.
- `integrity-check` without `--fix`: checks run without a full lock; if a move journal exists, recovery runs under lock.

---

## 4) Command reference

## 4.1 `init-project`

### Syntax
```bash
task-tracking init-project <project_id> [--statuses <csv>]
```

### Options
- `project_id` *(required)*
- `--statuses` *(default: `backlog,open,done`)*
  - CSV, trimmed, empty entries removed
  - must not be empty
  - no duplicates
  - each status must satisfy ID regex

### Behavior
- Creates project folders and a folder with empty `index.json` for each status.
- If project already exists: `CONFLICT` (Exit 4).

### Output (minimal example)
```json
{
  "ok": true,
  "project_id": "acme-s4",
  "statuses": ["backlog", "open", "done"]
}
```

---

## 4.2 `add`

### Syntax
```bash
task-tracking add <project_id>
  --task-id <task_id>
  [--status <status>]
  [--body "<text>"]
  [--tags "a,b,c"]
  [--assignee "<name>"]
  [--priority P0|P1|P2|P3]
  [--due-date <iso8601-date-or-datetime>]
```

### Defaults & Constraints
- `--task-id` required.
- `task_id` must satisfy ID regex `^[A-Za-z0-9_-]+$`.
- `task_id` must not already exist anywhere in the project.
- `--status` optional; Default is the **first** status in the lexicographically sorted project status list.
- `--tags`: CSV, split to `,`, trim per entry, discard empty entries.
- `--assignee`: must be string.
- `--priority`: only `P0..P3`.
- `--due-date`: ISO-8601 Date or DateTime.

### Output (minimal example)
```json
{
  "ok": true,
  "project_id": "acme-s4",
  "task_id": "fix_posting_logic",
  "status": "open"
}
```

---

## 4.3 `list`

### Syntax
```bash
task-tracking list <project_id>
  [--status <status>]
  [--tag <tag>]
  [--assignee <assignee>]
  [--priority P0|P1|P2|P3]
  [--filter-mode and|or]
  [--fields f1,f2,...]
  [--limit <int>]
  [--offset <int>]
  [--sort created_at|updated_at|priority|due_date]
  [--desc | --asc]
```

### Defaults & Constraints
- `limit` default `100`, must be `>0`, max `1000`.
- `offset` default `0`, must be `>=0`.
- `sort` default `updated_at`.
- `filter-mode` default `and`; allowed values: `and`, `or`.
- Sort order default `desc=true` (if neither `--desc` nor `--asc` is set).
- Allowed sort fields: `created_at`, `updated_at`, `priority`, `due_date`.

### Sorting (normative)
1. Values with an existing sort key (`present`) are sorted according to `(sort_value, task_id)`.
2. `--desc`/Default: `present` descending; `--asc`: ascending.
3. Values without a sort key (`missing`) **always come last**, internally ascending after `task_id`.
4. Tie breaker is `task_id`.

`due_date` is parsed for sorting as ISO Date/DateTime; unparseable values are considered `missing`.

### Filter/fields logic
- Filters are exact matches:
  - `tag`: must be contained in `tags`
  - `assignee`: exact string match
  - `priority`: exact string match
- `filter-mode` controls how active filters are combined:
  - `and` (default): all active filters must match
  - `or`: at least one active filter must match
- If none of `tag/assignee/priority` is provided, no value filter is applied.
- Default fields without `--fields`:
  - `task_id,status,priority,updated_at`
- For `--fields`: only desired fields, **but `task_id` and `status` are always added**.
- Allowed `--fields`: `task_id,status,created_at,updated_at,tags,assignee,priority,due_date`.
- Unknown field names cause `VALIDATION_ERROR`.

### Output (minimal example)
```json
{
  "ok": true,
  "project_id": "acme-s4",
  "count": 2,
  "count_total": 5,
  "items": [
    {
      "task_id": "fix_posting_logic",
      "status": "open",
      "priority": "P2",
      "updated_at": "2026-02-19T15:20:00+00:00"
    }
  ]
}
```
- `count`: number of returned items after `offset/limit`.
- `count_total`: number of matched items before pagination.

---

## 4.4 `show`

### Syntax
```bash
task-tracking show <project_id> <task_id>
  [--body]
  [--max-body-chars <int>=0+]
  [--max-body-lines <int>=0+]
```

### Defaults & Constraints
- Without `--body`: only meta.
- `max-body-chars` and `max-body-lines` must be `>=0` (if set).

### Truncation rules (normative)
If `--body` is active and both limits are set:
1. **first** `max-body-lines`
2. **after** `max-body-chars`

`body.truncated=true` as soon as at least one limit has cut.

### Output (minimal example with body)
```json
{
  "ok": true,
  "project_id": "acme-s4",
  "task_id": "fix_posting_logic",
  "status": "open",
  "meta": {
    "task_id": "fix_posting_logic",
    "created_at": "2026-02-19T15:00:00+00:00",
    "updated_at": "2026-02-19T15:20:00+00:00"
  },
  "body": {
    "text": "...",
    "truncated": true,
    "max_body_chars": 800,
    "max_body_lines": 50
  }
}
```

---

## 4.5 `move`

### Syntax
```bash
task-tracking move <project_id> <task_id> <new_status>
```

### Behavior
- Validates project/task/status.
- Writes Move Journal (`.tx_move.json`).
- Moves body file via `os.replace`.
- Updates source/target index.
- Updates `updated_at` in metadata; status is derived from the destination folder.

### Error cases (excerpt)
- Target status invalid: `VALIDATION_ERROR`.
- Task already in target status: `VALIDATION_ERROR`.
- Body missing / inconsistent index state: `INTEGRITY_ERROR`.

### Output (minimal example)
```json
{
  "ok": true,
  "project_id": "acme-s4",
  "task_id": "fix_posting_logic",
  "from": "open",
  "to": "done",
  "updated_at": "2026-02-19T16:00:00+00:00"
}
```

---

## 4.6 `meta-update`

### Syntax
```bash
task-tracking meta-update <project_id> <task_id>
  (--patch-json '<json>' | --stdin)
```

Exactly **one** patch source is allowed.

### Patch schema (operational)
```json
{
  "set": {
    "priority": "P1",
    "assignee": "Hannes",
    "tags": ["sap", "fi"]
  },
  "unset": ["due_date"]
}
```

### Constraints
- Exactly one source: `--patch-json` XOR `--stdin` (argument presence based, not truthiness).
- For `--stdin`:
  - if `stdin.isatty() == true` → `VALIDATION_ERROR` with message `stdin required` (no blocking read)
  - reads raw bytes via `sys.stdin.buffer.read()`
  - bytes are decoded strictly as UTF-8; decoding errors → `VALIDATION_ERROR` (`stdin must be valid UTF-8`)
- Patch must be JSON object.
- `set` (if present) must be an object.
- `unset` (if present) must be a list.
- Not patchable in `set` or `unset`:
  - `task_id`, `created_at`, `updated_at`, `status`, `title`
  - `status` is derived from the status folder.
  - `title` is not part of the task data model.
- `unset` elements: non-empty strings only.
- Type rules for `set`:
  - `tags`: list of non-empty strings
  - `assignee`: string
  - `priority`: `P0..P3`
  - `due_date`: string, ISO-8601 date/date-time
- Deletion is only performed via `unset` (not via `null`).

### Output (minimal example)
```json
{
  "ok": true,
  "project_id": "acme-s4",
  "task_id": "fix_posting_logic",
  "updated_at": "2026-02-19T16:05:00+00:00",
  "changed": {
    "set": ["assignee", "priority", "tags"],
    "unset": ["due_date"]
  }
}
```

---

## 4.7 `set-body`

### Syntax
```bash
task-tracking set-body <project_id> <task_id>
  (--text "<body>" | --file /path/to/file.md | --stdin)
```

### Constraints
- Exactly **one** source (`--text` XOR `--file` XOR `--stdin`).
- For `--file`: file must exist, otherwise `NOT_FOUND`.
- For `--stdin`:
  - if `stdin.isatty() == true` → `VALIDATION_ERROR` with message `stdin required` (no blocking read)
  - reads raw bytes via `sys.stdin.buffer.read()`
  - bytes are decoded strictly as UTF-8; decoding errors → `VALIDATION_ERROR` (`stdin must be valid UTF-8`)
- Body is completely replaced.
- `updated_at` is updated.

### Output (minimal example)
```json
{
  "ok": true,
  "project_id": "acme-s4",
  "task_id": "fix_posting_logic",
  "updated_at": "2026-02-19T16:10:00+00:00"
}
```

---

## 4.8 `integrity-check`

### Syntax
```bash
task-tracking integrity-check <project_id> [--fix]
```

### Behavior
- Checks project consistency across all statuses.
- If a move journal is present, recovery is attempted before checks (`recovered=true` when recovery ran).
- With `--fix`: conservative repairs (details in `references/architecture.md`).

### Return fields
- `ok`: `true` if no open issues remain.
- `recovered`: `true` if journal recovery ran.
- `fixed`: list of repairs actually performed.
- `issues`: open (unresolved) issues.
- `found`: all findings (including already fixed ones).

### Output (minimal example)
```json
{
  "ok": false,
  "project_id": "acme-s4",
  "recovered": true,
  "fixed": [
    {"type": "BODY_CREATED", "status": "open", "task_id": "fix_posting_logic"}
  ],
  "issues": [
    {"type": "ORPHAN_BODY", "status": "done", "task_id": "legacy_task"}
  ],
  "found": [
    {"type": "MISSING_BODY", "status": "open", "task_id": "fix_posting_logic"},
    {"type": "ORPHAN_BODY", "status": "done", "task_id": "legacy_task"}
  ]
}
```
