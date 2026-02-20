# Dateisystem-Layout (kanonisch)

## Root
- Für OpenClaw-Workspaces empfohlen: `TASK_TRACKING_ROOT=.task-tracking` (relativ zum Workspace-CWD).
- Effektiv ergibt das: `<workspace>/.task-tracking`.
- Falls `TASK_TRACKING_ROOT` **nicht** gesetzt ist, nutzt die CLI als Fallback `${CWD}/.task_tracking`.
- `TASK_TRACKING_ROOT` darf kein `..`-Segment enthalten.
- **Safe-Join:** alle abgeleiteten Pfade werden via `realpath` geprüft und müssen unter Root liegen.

## Projektstruktur

```text
<TASK_TRACKING_ROOT>/
  <project_id>/
    .lock                 # exklusiver Projekt-Lock (temporär während Operationen)
    .tx_move.json         # Move-Journal (nur während/bei Recovery relevant)
    <status_1>/
      index.json          # Metadaten-Map: { "<task_id>": <meta> }
      <task_id>.md        # Task-Body
    <status_2>/
      index.json
      <task_id>.md
    ...
```

## Regeln
- Statusliste wird **immer** aus vorhandenen Statusordnern abgeleitet (kein `project.json`).
- Pro Statusordner gibt es genau ein `index.json`.
- Jede Task existiert genau einmal: ein Indexeintrag + eine passende Body-Datei.
- `meta.status` muss dem Statusordner entsprechen.
- `meta.task_id` muss dem Index-Key und Dateinamen (`<task_id>.md`) entsprechen.
