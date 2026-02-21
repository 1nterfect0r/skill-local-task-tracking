# Task Tracking v1 — Test Plan (Structured)

> Goal: systematically check all CLI functions, error cases, recovery and `integrity-check --fix`.
> All output is **JSON** (stdout). Expected exit codes see below.

---

## 0) Requirements / Setup

**Optional test runner (Core + Regression + Edge):**
```bash
bash /home/hanneskuhl/.openclaw/skills/task-tracking/references/test_runner.sh
```
Log file is stored in the `/home/hanneskuhl/.openclaw/workspace/tmp/` folder.

**Storage location (workspace, recommended):**
- Set `TASK_TRACKING_ROOT=.task-tracking`
- Relative resolution via the OpenClaw workspace CWD:
  - `<workspace>/.task-tracking`

**`openclaw.json` (Best Practice):**
```json
{
  "skills": {
    "entries": {
      "task-tracking": {
        "enabled": true,
        "env": {
          "TASK_TRACKING_ROOT": ".task-tracking"
        }
      }
    }
  }
}
```

**Env & Root (for this test plan, isolated):**
```bash
export TASK_TRACKING_ROOT=/tmp/tt-root
baseDir=/home/hanneskuhl/.openclaw/skills/task-tracking
# Replace {baseDir} below with this path.
rm -rf /tmp/tt-root
```

**Conventions:**
- `<ISO>` = any ISO‑8601 UTC timestamp
- `<ROOT>` = `/tmp/tt-root`
- Status order: `backlog,open,done`

**Exit Codes:**
- `0` OK
- `2` VALIDATION_ERROR
- `3` NOT_FOUND
- `4` CONFLICT
- `5` INTEGRITY_ERROR
- `10` UNEXPECTED_ERROR

---

## 1) `init-project`

### 1.1 Success
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py init-project acme-s4 --statuses backlog,open,done
```
**Expected JSON**
```json
{ "ok": true, "project_id": "acme-s4", "statuses": ["backlog","open","done"] }
```
**Expected FS**
```
<ROOT>/acme-s4/
  backlog/index.json   # {}
  open/index.json      # {}
  done/index.json      # {}
```

### 1.2 Conflict
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py init-project acme-s4
```
**Expected JSON**
```json
{ "ok": false, "error": { "code": "CONFLICT", "message": "Project already exists" } }
```
**Exit Code:** `4`

---

## 2) `add`

### 2.1 Add default status (backlog)
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id fix_posting_logic
```
**Expected JSON**
```json
{ "ok": true, "project_id": "acme-s4", "task_id": "fix_posting_logic", "status": "backlog" }
```
**Expected FS**
```
<ROOT>/acme-s4/backlog/index.json
<ROOT>/acme-s4/backlog/fix_posting_logic.md   # empty
```
`index.json` contains entry with fields `task_id,created_at,updated_at` (status derived from folder).

### 2.2 Add with explicit status + metadata
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id adjust_tax_codes --status open --tags "sap,fi" --assignee hannes --priority P2 --body "Initial body"
```
**Expected JSON**
```json
{ "ok": true, "project_id": "acme-s4", "task_id": "adjust_tax_codes", "status": "open" }
```
**Expected FS**
```
<ROOT>/acme-s4/open/adjust_tax_codes.md  # "Initial body"
<ROOT>/acme-s4/open/index.json          # contains meta with tags/assignee/priority
```

### 2.3 Task-ID uniqueness
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id fix_posting_logic
```
**Expected JSON**
```json
{ "ok": false, "error": { "code": "CONFLICT", "message": "Task ID already exists" } }
```
**Exit Code:** `4`

### 2.4 Validation errors
- Invalid ID / status (e.g. spaces, `..`) → `VALIDATION_ERROR` (exit 2)
- Invalid priority → `VALIDATION_ERROR`
- Duplicate `task_id` → `CONFLICT` (exit 4)

---

## 3) `list`

### 3.1 Default list
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --limit 100 --sort updated_at --desc
```
**Expected JSON (shape)**
```json
{ "ok": true, "project_id": "acme-s4", "count": 3, "count_total": 3, "items": [ {"task_id":"...","status":"...","priority":null,"updated_at":"<ISO>"}, ... ] }
```
**Expected Behavior**
- Sorted by `updated_at` desc.
- Fields default to `task_id,status,priority,updated_at`.
- `count` is post-pagination; `count_total` is pre-pagination.

### 3.2 Filters & fields
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --status open --fields task_id,assignee --limit 10
```
**Expected JSON**
- `items` contain only requested fields + enforced `task_id,status`.

### 3.3 Pagination
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --limit 1 --offset 1
```
**Expected JSON**
- Exactly 1 item returned (`count=1`).
- `count_total` remains the full match count (before pagination).

### 3.4 Filter combination with `--filter-mode and`
**Setup hint:** Ensure at least one task matches both filters and at least one task matches only one filter.

**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --tag sap --assignee hannes --filter-mode and --limit 100
```
**Expected JSON**
- Only tasks that satisfy **both** filters are returned.
- `assignee` matching is exact (case-sensitive).

### 3.5 Filter combination with `--filter-mode or`
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --tag sap --assignee hannes --filter-mode or --limit 100
```
**Expected JSON**
- Tasks that satisfy **at least one** of the filters are returned.
- Result count is typically greater than or equal to the `and` variant.

---

## 4) `show`

### 4.1 Meta only
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py show acme-s4 adjust_tax_codes
```
**Expected JSON**
```json
{ "ok": true, "project_id": "acme-s4", "task_id": "adjust_tax_codes", "status": "open", "meta": { "task_id":"adjust_tax_codes", "created_at":"<ISO>", "updated_at":"<ISO>", "tags":["sap","fi"], "assignee":"hannes", "priority":"P2" } }
```

### 4.2 Body with limits
**Setup**
```bash
python3 {baseDir}/scripts/task_tracking.py set-body acme-s4 adjust_tax_codes --text "L1\nL2\nL3\nL4"
```
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py show acme-s4 adjust_tax_codes --body --max-body-lines 2 --max-body-chars 5
```
**Expected JSON (shape)**
```json
{ "ok": true, "body": { "text": "L1\nL2", "truncated": true, "max_body_lines": 2, "max_body_chars": 5 } }
```

---

## 5) `move`

### 5.1 Move open → done
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py move acme-s4 adjust_tax_codes done
```
**Expected JSON**
```json
{ "ok": true, "project_id": "acme-s4", "task_id": "adjust_tax_codes", "from": "open", "to": "done", "updated_at": "<ISO>" }
```
**Expected FS**
```
<ROOT>/acme-s4/done/adjust_tax_codes.md   # body moved
<ROOT>/acme-s4/open/adjust_tax_codes.md   # gone
```
`done/index.json` contains task with `status=done`.

### 5.2 Move to same status → validation error
**Expected:** `VALIDATION_ERROR` (exit 2)

### 5.3 Destination index conflict (manual corruption)
**Setup**
- Add a duplicate entry manually to `done/index.json` for `fix_posting_logic`
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py move acme-s4 fix_posting_logic done
```
**Expected:** **OK** (exit 0) — Auto‑Fix runs before the move and resolves the duplicate. If you want to test the raw conflict, run `integrity-check` directly (without `--fix`) to observe the issue before an operation.

---

## 6) `meta-update`

### 6.1 Valid patch
**Command**
```bash
echo '{"set":{"priority":"P1","assignee":"Hannes"},"unset":["due_date"]}' | \
  python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 fix_posting_logic --stdin
```
**Expected JSON**
```json
{ "ok": true, "project_id": "acme-s4", "task_id": "fix_posting_logic", "updated_at": "<ISO>", "changed": { "set": ["priority","assignee"], "unset": ["due_date"] } }
```

### 6.2 Forbidden fields
**Command**
```bash
echo '{"set":{"status":"done"}}' | python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 fix_posting_logic --stdin
```
**Expected:** `VALIDATION_ERROR` (exit 2)

### 6.3 Empty `--patch-json` → invalid JSON
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 fix_posting_logic --patch-json ""
```
**Expected:** `VALIDATION_ERROR` (exit 2), message `Invalid JSON patch`

### 6.4 Invalid UTF-8 on `--stdin` → `VALIDATION_ERROR`
**Command**
```bash
python3 -c 'import sys; sys.stdout.buffer.write(b"\xff")' | python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 fix_posting_logic --stdin
```
**Expected:** `VALIDATION_ERROR` (exit 2), message `stdin must be valid UTF-8`

### 6.5 `--stdin` with TTY stdin → `VALIDATION_ERROR` (`stdin required`, no blocking read)

---

## 7) `set-body`

### 7.1 From text
```bash
python3 {baseDir}/scripts/task_tracking.py set-body acme-s4 fix_posting_logic --text "Hello"
```
**Expected JSON**
```json
{ "ok": true, "project_id": "acme-s4", "task_id": "fix_posting_logic", "updated_at": "<ISO>" }
```
**Expected FS**
```
<ROOT>/acme-s4/backlog/fix_posting_logic.md   # content = "Hello"
```

### 7.2 From file
```bash
echo "File body" > /tmp/body.md
python3 {baseDir}/scripts/task_tracking.py set-body acme-s4 fix_posting_logic --file /tmp/body.md
```

### 7.3 From stdin
```bash
printf "stdin body\n" | python3 {baseDir}/scripts/task_tracking.py set-body acme-s4 fix_posting_logic --stdin
```

### 7.4 Invalid UTF-8 on stdin → `VALIDATION_ERROR`
```bash
python3 -c 'import sys; sys.stdout.buffer.write(b"\xff")' | python3 {baseDir}/scripts/task_tracking.py set-body acme-s4 fix_posting_logic --stdin
```

### 7.5 `--stdin` with TTY stdin → `VALIDATION_ERROR` (`stdin required`, no blocking read)

### 7.6 Invalid arguments (multiple or none) → `VALIDATION_ERROR`

---

## 8) `integrity-check` (no fix)

### 8.1 Clean state
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py integrity-check acme-s4
```
**Expected JSON**
```json
{ "ok": true, "project_id": "acme-s4", "recovered": false, "fixed": [], "issues": [] }
```

### 8.2 Detect issues (prepare corrupt state)
**Setup (manual):**
- Delete a body file: `rm <ROOT>/acme-s4/backlog/fix_posting_logic.md`
- Create orphan body: `echo "orphan" > <ROOT>/acme-s4/open/orphan.md`
- Duplicate index: add `fix_posting_logic` to `done/index.json` with older `updated_at`
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py integrity-check acme-s4
```
**Expected JSON (shape)**
```json
{ "ok": false, "issues": [ {"type":"MISSING_BODY",...}, {"type":"ORPHAN_BODY",...}, {"type":"DUPLICATE_TASK",...} ] }
```

---

## 9) `integrity-check --fix`

**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py integrity-check acme-s4 --fix
```
**Expected Fixes (A,1):**
- **Duplicates:** keeps entry with **latest `updated_at`**, removes older one from other states.
- **orphan‑Body:** creates index entry with minimal meta (if ID does not exist anywhere else).
- **Missing Body:** creates empty `.md`.

**Expected JSON (shape)**
```json
{ "ok": true, "project_id": "acme-s4", "recovered": false, "fixed": [ ... ], "issues": [ ... ], "found": [ ... ] }
```
**Note:** `ok` is **true** if all issues were resolved by `--fix`. `issues` contains only unresolved problems; `found` contains all detected issues.
**Expected FS after fix**
- Duplicates reduced to one status.
- orphan now has an index entry.
- Missing body files exist again.

---

## 10) Recovery / Journal (`.tx_move.json`)

### 10.1 Simulated Crash
**Setup (manual):**
- Create `.tx_move.json` with valid content (`op=move`, `task_id`, `from`, `to`, `updated_meta`)
- Move the body to target state, **without** index update

**Action**
- Call `list` or `show` (triggers recovery)

**Expected:**
- Journal is cleared
- Body + Index consistent
- `.tx_move.json` removed

---

## 11) Locking / Stale Lock

### 11.1 Stale Lock
**Setup**
```bash
echo '{"pid":999999}' > <ROOT>/acme-s4/.lock
```
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id lock_test
```
**Expected:**
- Lock is recognized as stale → operation succeeds

---

## 12) Negative Tests (Validation)

- Invalid project_id / task_id / status → `VALIDATION_ERROR`
- Non‑existent project → `NOT_FOUND`
- Non‑existent task → `NOT_FOUND`
- Invalid `--sort` → `VALIDATION_ERROR`
- Invalid `--filter-mode` → `VALIDATION_ERROR`
- `--limit <= 0` or `--offset < 0` → `VALIDATION_ERROR`
- `--limit > 1000` → `VALIDATION_ERROR`
- `TASK_TRACKING_ROOT` contains `..` segment(s) → `VALIDATION_ERROR`

---

## 13) Determinism / JSON Shape

- JSON keys stabil (best effort). Compare only required keys & types.
- Timestamps: ISO‑8601 UTC strings.
- `list` ordering stable for equal sort values (`task_id` tiebreak).

---

## 14) Additional Coverage (Code‑driven)

### 14.1 `list --asc`
**Setup:** Ensure you have two tasks with known `updated_at` (or adjust in index).
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --sort updated_at --asc --limit 10
```
**Expected:** ascending order by `updated_at`, `task_id` as tiebreak.

### 14.2 Filters: `--tag` / `--assignee` / `--priority`
**Commands**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --tag sap --limit 100
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --assignee hannes --limit 100
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --priority P2 --limit 100
```
**Expected:** items subset matches filter.

### 14.3 `add --due-date` valid + invalid
**Commands**
```bash
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id task_a --due-date 2026-03-01
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id task_b --due-date 2026-03-01T12:34:56Z
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id bad_due --due-date 2026-02-30
```
**Expected:** first two ok; last returns `VALIDATION_ERROR` (exit 2).

### 14.4 `meta-update --patch-json` (+ invalid JSON)
**Command (valid)**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{"priority":"P1"},"unset":[]}'
```
**Expected:** ok, `changed.set` includes `priority`.

**Command (invalid JSON)**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{bad}'
```
**Expected:** `VALIDATION_ERROR` (exit 2).

### 14.5 `set-body --file` not found
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py set-body acme-s4 task_a --file /tmp/no-such-file.md
```
**Expected:** `NOT_FOUND` (exit 3).

### 14.6 CLI-Fallback-Root (no `TASK_TRACKING_ROOT`)
**Setup**
```bash
unset TASK_TRACKING_ROOT
rm -rf .task_tracking
```
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py init-project local-test
```
**Expected FS**
```
<CWD>/.task_tracking/local-test/...
```
**Note:** For OpenClaw productive, continue to use `TASK_TRACKING_ROOT=.task-tracking` (workspace-local).

### 14.7 Active Lock (non‑stale)
**Setup**
```bash
python3 - <<'PY'
import json,os
with open('/tmp/tt-root/acme-s4/.lock','w') as f:
    f.write(json.dumps({'pid': os.getpid()}))
PY
```
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id lock_active
```
**Expected:** `CONFLICT` (exit 4).

### 14.8 integrity-check additional issue types
**Setup (examples, manual):**
- Corrupt an index file (e.g., write `[]`) → `INDEX_ERROR`
- Set a task meta to a non‑object (e.g., string) → `META_NOT_OBJECT`
- Mismatch `task_id` inside meta → `TASK_ID_MISMATCH`
- (Optional legacy-data check) Inject extra unknown fields in `meta` and verify they do not break commands
- Remove required fields (`created_at`, etc.) → `MISSING_FIELD`
- Corrupt known field types:
  - `tags` not list/non-empty strings → `TAGS_INVALID`
  - `assignee` non-string → `ASSIGNEE_INVALID`
  - invalid `priority` value/type → `PRIORITY_INVALID`
  - invalid `due_date` value/type → `DUE_DATE_INVALID`
  - `created_at` / `updated_at` non-string → `FIELD_TYPE_INVALID`
- Remove a status directory → `STATUS_DIR_MISSING`
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py integrity-check acme-s4 --fix
```
**Expected:** issues reported; fixes applied where possible (e.g., `META_REPLACED`, `TASK_ID_FIXED`, `FIELD_FILLED`, `TAGS_NORMALIZED`, `ASSIGNEE_REMOVED`, `PRIORITY_REMOVED`, `DUE_DATE_REMOVED`, `FIELD_TYPE_FIXED`).

### 14.9 Duplicate resolution without `updated_at`
**Setup:** create duplicate task in multiple statuses **without** `updated_at`.
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py integrity-check acme-s4 --fix
```
**Expected:** winner chosen by project status order (`rule: status_order`).

### 14.10 `list` filter mode semantics (`and` vs `or`)
**Setup:**
- Task A matches only `tag=sap`
- Task B matches only `assignee=hannes`
- Task C matches both

**Commands**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --tag sap --assignee hannes --filter-mode and --limit 100
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --tag sap --assignee hannes --filter-mode or --limit 100
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --tag sap --assignee hannes --limit 100
```
**Expected:**
- `and` returns only Task C
- `or` returns A, B, C
- Omitted `--filter-mode` behaves like `and`

---

## 15) Additional Edge Cases (Implementation‑specific)

### 15.1 `show --body` with missing body file
**Setup:** delete an existing body file.
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py show acme-s4 task_a --body
```
**Expected:** **OK** (exit 0). Auto‑Fix recreates the missing body before `show` runs.

### 15.2 `add` when body file exists without index
**Setup:**
```bash
echo "orphan" > <ROOT>/acme-s4/backlog/orphan_body.md
```
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id orphan_body
```
**Expected:** `CONFLICT` (exit 4) — Auto‑Fix indexes the orphan body before `add`, so the task ID already exists.

### 15.3 `list --fields` without `task_id/status`
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --fields updated_at --limit 10
```
**Expected:** items still include `task_id` and `status`.

### 15.4 `list --sort due_date` with missing values
**Setup:** ensure at least one task with `due_date` and one without.
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --sort due_date --asc --limit 10
```
**Expected:** entries without `due_date` sort last; missing‑group is sorted by `task_id`.

### 15.5 `list --status` valid but missing status
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --status qa --limit 10
```
**Expected:** `NOT_FOUND` (exit 3).

### 15.6 `move` to non‑existent status
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py move acme-s4 task_a qa
```
**Expected:** `VALIDATION_ERROR` (exit 2).

### 15.7 `meta-update` invalid patch format
**Commands**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":[],"unset":[]}'
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{},"unset":"x"}'
```
**Expected:** `VALIDATION_ERROR` (exit 2).

### 15.8 `meta-update` tags validation
**Commands**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{"tags":"sap"}}'
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{"tags":["", "sap"]}}'
```
**Expected:** `VALIDATION_ERROR` (exit 2).

### 15.9 Lock file invalid JSON
**Setup**
```bash
echo 'not-json' > <ROOT>/acme-s4/.lock
```
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id lock_invalid
```
**Expected:** `CONFLICT` (exit 4).

### 15.10 integrity‑check orphan body with existing task_id elsewhere
**Setup:** create an orphan body in a different status **using an existing task_id**.
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py integrity-check acme-s4 --fix
```
**Expected:** `ORPHAN_BODY` reported, **no** `ORPHAN_INDEX_CREATED` for that ID.

**Cleanup (before 15.14):** remove the orphan body you created here, otherwise later `list` tests may fail due to unresolved integrity issues.
```bash
rm <ROOT>/acme-s4/open/<existing_task_id>.md
```

### 15.11 `show` with negative max values
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py show acme-s4 task_a --body --max-body-chars -1
python3 {baseDir}/scripts/task_tracking.py show acme-s4 task_a --body --max-body-lines -1
```
**Expected:** `VALIDATION_ERROR` (exit 2) for each.

### 15.12 integrity‑check fixes missing index file
**Setup:** delete `<ROOT>/acme-s4/open/index.json`.
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py integrity-check acme-s4 --fix
```
**Expected:** `INDEX_ERROR` reported + `INDEX_CREATED` in `fixed`.

### 15.13 Recovery: invalid tx status not in project
**Setup:** create `.tx_move.json` with `from/to` not in project statuses.
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --limit 1
```
**Expected:** `INTEGRITY_ERROR` (exit 5) with `Invalid transaction status`.

### 15.14 `list --sort due_date` with invalid `due_date`
**Setup (manual):** set `due_date` to an invalid string in `index.json` of a task.
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --sort due_date --asc --limit 10
```
**Expected:** no crash; entries with invalid `due_date` are treated as "missing" (at the end of the list). **Important:** make sure there are no open integrity issues, otherwise `list` can abort with `INTEGRITY_ERROR` (auto-fix blocks when problems are not resolvable).

### 15.15 `list --sort due_date` with non-string `due_date`
**Setup (manual):** set `due_date` to a non-string value (e.g., number) in `index.json`.
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --sort due_date --asc --limit 10
```
**Expected:** no crash; malformed `due_date` values are treated as "missing".

### 15.16 `list` with malformed `tags` under filter mode
**Setup (manual):** set `tags` of a task to a non-list value in `index.json` (e.g., `123`).
**Commands**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --tag sap --assignee hannes --filter-mode or --limit 100
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --tag sap --filter-mode and --limit 100
```
**Expected:**
- no crash
- malformed `tags` are treated as non-matching for `tag` filter
- other filters still work (`or` can still match on `assignee`)

---

## 16) Happy‑Path End‑to‑End

**Setup**
```bash
export TASK_TRACKING_ROOT=/tmp/tt-root
rm -rf /tmp/tt-root
```

**Flow**
```bash
python3 {baseDir}/scripts/task_tracking.py init-project acme-s4 --statuses backlog,open,done
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id ingest_invoice_feed --tags "finance,etl" --assignee hannes --priority P2 --due-date 2026-03-15
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --task-id fix_posting_logic
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --limit 10
python3 {baseDir}/scripts/task_tracking.py show acme-s4 ingest_invoice_feed
python3 {baseDir}/scripts/task_tracking.py set-body acme-s4 ingest_invoice_feed --text "Initial spec"
python3 {baseDir}/scripts/task_tracking.py move acme-s4 ingest_invoice_feed open
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 ingest_invoice_feed --patch-json '{"set":{"priority":"P1"},"unset":[]}'
python3 {baseDir}/scripts/task_tracking.py show acme-s4 ingest_invoice_feed --body
python3 {baseDir}/scripts/task_tracking.py integrity-check acme-s4
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --status open --limit 10
```

**Expected:** all commands return `ok: true` and exit code `0`; final list shows `ingest_invoice_feed` in `open` with updated priority and body present.

---

## 17) Clean‑Up
```bash
rm -rf /tmp/tt-root
```

---

## 18) Additional Edge Cases (post‑hardening)

### 18.1 `meta-update` set tags = null
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{"tags":null},"unset":[]}'
```
**Expected:** `VALIDATION_ERROR` (exit 2)

### 18.2 `meta-update` set assignee non-string
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{"assignee":123},"unset":[]}'
```
**Expected:** `VALIDATION_ERROR` (exit 2)

### 18.3 `meta-update` set due_date null
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{"due_date":null},"unset":[]}'
```
**Expected:** `VALIDATION_ERROR` (exit 2)

### 18.4 `meta-update` unset contains non-string
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{},"unset":["due_date",123]}'
```
**Expected:** `VALIDATION_ERROR` (exit 2)

### 18.5 `meta-update` set priority null
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{"priority":null},"unset":[]}'
```
**Expected:** `VALIDATION_ERROR` (exit 2)

### 18.6 `meta-update` set title is forbidden
**Commands**
```bash
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{"title":123},"unset":[]}'
python3 {baseDir}/scripts/task_tracking.py meta-update acme-s4 task_a --patch-json '{"set":{"title":""},"unset":[]}'
```
**Expected:** `VALIDATION_ERROR` (exit 2)

### 18.7 `list` auto-repairs non-object meta via preflight fix
**Setup (manual):** set an index entry to a string instead of an object.
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --limit 10
```
**Expected:** no crash; Preflight `integrity-check --fix` replaces the incorrect meta entry with minimal meta (`META_REPLACED`). The task can then appear in `items`.

### 18.8 `integrity-check` no orphan flood without index
**Setup (manual):** delete `<ROOT>/<project>/<status>/index.json` and create a few `*.md` bodies.
**Command**
```bash
python3 {baseDir}/scripts/task_tracking.py integrity-check acme-s4
```
**Expected:** `INDEX_ERROR` for status; **no** `ORPHAN_BODY` messages for the same status.

### 18.9 Guard: `TASK_TRACKING_ROOT` cannot contain `..`
**Command**
```bash
TASK_TRACKING_ROOT=../escape python3 {baseDir}/scripts/task_tracking.py list acme-s4 --limit 1
```
**Expected:** `VALIDATION_ERROR` (exit 2)
