---
name: task-tracking
description: Local filesystem Kanban task tracking CLI with deterministic JSON stdout (init-project/add/list/show/move/meta-update/set-body).
metadata: {"openclaw":{"requires":{"anyBins":["python3","python"]}}}
---

# Task-Tracking (Skill)

## Purpose
Manage tasks locally on the filesystem per project using a Python CLI designed for automation:
- **stdout is always JSON** (success and error)
- deterministic behavior where feasible
- atomic operations and locking

## Use cases
Use this skill to:
- maintain a simple Kanban-style workflow per project (e.g., backlog/open/done)
- drive task workflows from agents/pipelines via deterministic JSON output
- keep deterministic task workflows across repeated automated runs

Do **not** use this skill for:
- SaaS/network integrations (ticketing systems, APIs, webhooks)
- multi-user concurrent editing without shared filesystem semantics
- complex querying beyond provided CLI filters

---

## Invocation
- CLI entrypoint: `python3 {baseDir}/scripts/task_tracking.py <command> ...`
- `baseDir` is the OpenClaw-provided skill root (directory containing this `SKILL.md`).

---

## Storage (TASK_TRACKING_ROOT) — workspace-local by design
This skill is intended to be used **per OpenClaw workspace**. Configure `TASK_TRACKING_ROOT` as a **relative path** so each workspace gets its own independent store.

**Recommended:**
- `TASK_TRACKING_ROOT=.task-tracking` → resolves to `<workspace>/.task-tracking`


### Configure via `openclaw.json` (best practice)
Set the environment variable via OpenClaw configuration so it is injected consistently per run.

Add to `~/.openclaw/openclaw.json`:
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

---

## Tool contract (automation-critical)

### Output channels
- **stdout:** Always JSON (success and error)
- **stderr:** Should be empty (unexpected debug output only)

### Exit codes (stable)
- `0` OK
- `2` ValidationError
- `3` NotFound
- `4` Conflict (e.g., task-id exists; lock held)
- `5` IntegrityError
- `10` UnexpectedError

### Error JSON shape (stable)
```json
{
  "ok": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Task not found",
    "details": { "project_id": "...", "task_id": "..." }
  }
}
```

### Success JSON (convention)
- `ok: true` plus command-specific fields.

---

## Core concepts (must-know)
- `task_id` is the canonical identifier.
- `title` is **derived** from `task_id` (underscores ↔ spaces); **title is not stored**.
- Collision handling in `add` is deterministic using suffixes `-2`, `-3`, …
- Commands may run a preflight integrity repair.

---

## Core workflow (recommended)
1) `init-project` (once per project)
2) `add`
3) `list` (filter/sort/fields)
4) `show` (optional body limits)
5) `set-body`
6) `meta-update`
7) `move`

---

## Quick start
set TASK_TRACKING_ROOT via ~/.openclaw/openclaw.json (see above)   
```bash
python3 {baseDir}/scripts/task_tracking.py init-project acme-s4 --statuses backlog,open,done
python3 {baseDir}/scripts/task_tracking.py add acme-s4 --title "Fix posting logic"
python3 {baseDir}/scripts/task_tracking.py list acme-s4 --limit 20
python3 {baseDir}/scripts/task_tracking.py show acme-s4 fix_posting_logic --body --max-body-lines 50 --max-body-chars 800
```

---

## Commands (cheat sheet)
- `init-project <project_id> [--statuses backlog,open,done]` — initialize a project and status columns
- `add <project_id> --title "..." [--status <status>] [--task-id <id>] [--body "..."] [--tags "a,b,c"]` — create task
- `list <project_id> [filters...] [--fields a,b,c] [--limit N] [--offset K] [--sort <field>] [--desc]` — list tasks
- `show <project_id> <task_id> [--body] [--max-body-chars N] [--max-body-lines N]` — show task
- `move <project_id> <task_id> <new_status>` — move task across columns (atomic)
- `meta-update <project_id> <task_id> [--patch-json '{...}'] [--patch-stdin]` — patch metadata
- `set-body <project_id> <task_id> (--text "...") | (--file /path/to/body.md)` — replace body

---

## Operational guidance (agent behavior)
- Always parse stdout JSON and branch on `ok`.
- Treat exit code as secondary; prefer `error.code` for logic.
- On `Conflict` (exit 4): retry only when the workflow expects lock contention.

---

## References (load only if needed)
- `references/cli_reference.md` — full CLI options, filters, defaults, detailed outputs, exit-code details
- `references/metadata_schema.md` — metadata fields and constraints (incl. patchable vs. non-patchable)
- `references/filesystem_layout.md` — on-disk layout
- `references/architecture.md` — recovery and journaling internals
- `references/design_scope.md` — scope / non-goals
- `references/test_plan.md` — structured test plan
- `references/test_log_2026-02-19.md` — executed test log
