# Filesystem Layout (canonical)

## Root
- Recommended for OpenClaw workspaces: `TASK_TRACKING_ROOT=.task-tracking` (relative to the workspace CWD).
- This resolves to: `<workspace>/.task-tracking`.
- If `TASK_TRACKING_ROOT` is **not** set, the CLI falls back to `${CWD}/.task_tracking`.
- `TASK_TRACKING_ROOT` must not contain a `..` segment.
- **Safe join:** all derived paths are checked via `realpath` and must stay under the root.

## Project structure

```text
<TASK_TRACKING_ROOT>/
  <project_id>/
    .lock                 # exclusive project lock (temporary during operations)
    .tx_move.json         # move journal (relevant during/for recovery)
    <status_1>/
      index.json          # metadata map: { "<task_id>": <meta> }
      <task_id>.md        # task body
    <status_2>/
      index.json
      <task_id>.md
    ...
```

## Rules
- The status list is **always** derived from existing status folders (no `project.json`).
- There is exactly one `index.json` per status folder.
- Each task exists exactly once: one index entry + one matching body file.
- `status` is derived from the status folder name (it is not stored in `meta`).
- `meta.task_id` must match the index key and filename (`<task_id>.md`).
