# Task Tracking (Option 1, v1) – Goal, Scope, Concept (Developer)

> Architecture/Scope reference for registered skill `task-tracking` (implementation under `scripts/`).

## 0. Target & Scope (v1)
**Aim:** Local, file system-based task tracking for multiple projects. All mutations run deterministically via a Python CLI. **No network access.**

**In Scope (v1):**
- Project initialization
- Create task
- List tasks (filterable, limited)
- Show task (meta default; body opt‑in, limited)
- Move task to different state (atomic)
- Update metadata (robust, patch-oriented)
- Set/replace body (text or file)

**Out of Scope (v1):**
- Delete/Archive
- Remote/SaaS integration, Sync, Notifications, Calendar
- Automatic status transitions
- Reporting/Exports
- Human output (tables or similar) – **v1 only returns JSON on stdout**

## 1. Terminology
- **Project:** Collection of tasks under `project_id`.
- **Status:** State of a task (configured set; default e.g. `backlog`, `open`, `done`).
- **Task:** consists of **Body** (`{task_id}.md`) and **Metadata** (entry in `index.json` of the respective status folder).
  - `status` is derived from the folder and not persisted in metadata.

## 2. Configuration & Path Rules
- **Root (OpenClaw recommended):** `TASK_TRACKING_ROOT=.task-tracking` (relative to workspace CWD, effective `<workspace>/.task-tracking`).
- **Fallback of CLI:** if `TASK_TRACKING_ROOT` is not set, `${CWD}/.task_tracking`.
- **Safety rule:** Never read/write outside root (prevent path traversal).
- **Identifiers:** `project_id` and `task_id` must match `^[A-Za-z0-9_-]+$`. No separators, no `..`, no spaces.
- **Status names:** also `^[A-Za-z0-9_-]+$`.
  - v1 default status list at initialization (e.g. `backlog,open,done`).
  - Status list is **always** derived from the existing status folders.

## 3. Canonical Layout (Quick Overview)
```
<TASK_TRACKING_ROOT>/
  <project_id>/
    backlog/
      index.json
      <task_id>.md
    open/
      index.json
      <task_id>.md
    done/
      index.json
      <task_id>.md
```
**Rule:** per status folder there is exactly **one** `index.json` that holds all metadata in this status.

## 4. Non-functional requirements
- **Portability:** Python 3.10+, Windows/Linux/macOS.
- **Determinism:** stable JSON structures, stable sorting logic.
- **Performance:** `list` must remain controllable via status filter/limit.
- **Error robustness:** Validation errors provide structured JSON error objects; no stack traces in stdout.

Further detail: see `filesystem_layout.md`, `metadata_schema.md`, `cli_reference.md`, `architecture.md`.
