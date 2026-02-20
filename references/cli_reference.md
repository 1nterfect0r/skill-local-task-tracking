# CLI-Referenz (normativ, v1)

## Inhaltsverzeichnis
- [1) Globale Konventionen](#1-globale-konventionen)
- [2) Exit Codes und error.code](#2-exit-codes-und-errorcode)
- [3) Locking-/Conflict-Semantik](#3-locking--conflict-semantik)
- [4) Command-Referenz](#4-command-referenz)
  - [4.1 init-project](#41-init-project)
  - [4.2 add](#42-add)
  - [4.3 list](#43-list)
  - [4.4 show](#44-show)
  - [4.5 move](#45-move)
  - [4.6 meta-update](#46-meta-update)
  - [4.7 set-body](#47-set-body)
  - [4.8 integrity-check](#48-integrity-check)

## 1) Globale Konventionen

### 1.1 Ausgabeformat
- `stdout`: immer genau **ein JSON-Objekt**.
- Fehler sind ebenfalls JSON:

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
- `TASK_TRACKING_ROOT` steuert den Root-Pfad.
- Wenn nicht gesetzt: `${CWD}/.task_tracking`.
- Wenn gesetzt: Pfad wird absolut aufgelöst.
- `TASK_TRACKING_ROOT` darf kein `..`-Segment enthalten (sonst `VALIDATION_ERROR`, Exit 2).

### 1.3 ID-/Status-Validierung
- `project_id`, `task_id`, `status` folgen Regex: `^[A-Za-z0-9_-]+$`.

### 1.4 Title-/Task-ID-Regel
- `title` ist **nur I/O-Repräsentation** von `task_id`:
  - Input: Spaces werden zu `_` normalisiert.
  - Output: `_` wird zu Spaces.
- `title` wird nicht persistent im Index gespeichert.

---

## 2) Exit Codes und error.code

| Exit | error.code        | Bedeutung |
|---:|---|---|
| 0  | *(kein error-Objekt)* | Erfolg |
| 2  | `VALIDATION_ERROR` | Ungültige Argumente/Inputs/Schema |
| 3  | `NOT_FOUND` | Projekt/Task/Datei nicht gefunden |
| 4  | `CONFLICT` | Konflikt (u. a. Lock aktiv, Duplicate-ID) |
| 5  | `INTEGRITY_ERROR` | Dateninkonsistenz erkannt |
| 10 | `UNEXPECTED_ERROR` | Nicht klassifizierter Laufzeitfehler |

Hinweis: Agenten können robust auf **beides** prüfen (`exit_code` und `error.code`).

---

## 3) Locking-/Conflict-Semantik

### 3.1 Projekt-Lock
Die meisten Projektoperationen arbeiten mit exklusivem Lockfile `<project_dir>/.lock`.

- Bei aktivem Lock: `CONFLICT` (Exit 4) mit Details:

```json
{
  "lock": "/.../<project>/.lock",
  "reason": "LOCKED"
}
```

- Stale-Lock-Recovery: Wenn PID aus dem Lockfile nicht mehr lebt, versucht der Service den Lock zu brechen und neu zu übernehmen.

### 3.2 Lock-Verhalten pro Command
- Immer unter Projekt-Lock: `add`, `list`, `show`, `move`, `meta-update`, `set-body`.
- `integrity-check --fix`: unter Projekt-Lock.
- `integrity-check` ohne `--fix`: Checks selbst ohne Full-Lock; falls ein Move-Journal vorliegt, läuft Recovery unter Lock.

---

## 4) Command-Referenz

## 4.1 `init-project`

### Syntax
```bash
task-tracking init-project <project_id> [--statuses <csv>]
```

### Optionen
- `project_id` *(required)*
- `--statuses` *(default: `backlog,open,done`)*
  - CSV, getrimmt, leere Einträge entfernt
  - muss nicht leer sein
  - keine Duplikate
  - jeder Status muss ID-Regex erfüllen

### Verhalten
- Erstellt Projektordner und pro Status einen Ordner mit leerem `index.json`.
- Wenn Projekt bereits existiert: `CONFLICT` (Exit 4).

### Output (Minimalbeispiel)
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
  --title "<title>"
  [--status <status>]
  [--task-id <task_id>]
  [--body "<text>"]
  [--tags "a,b,c"]
  [--assignee "<name>"]
  [--priority P0|P1|P2|P3]
  [--due-date <iso8601-date-or-datetime>]
```

### Defaults & Constraints
- `--title` required, String, nach Trim/Kollaps nicht leer.
- `task_id` wird aus `title` abgeleitet (`spaces -> _`).
- Title mit `_` ist unzulässig (`Title must use spaces instead of underscores`).
- Bei explizitem `--task-id`:
  - muss regex-valid sein,
  - muss exakt zum normalisierten Titel passen,
  - darf global im Projekt nicht existieren.
- Ohne `--task-id`:
  - auto-generiert aus `title`,
  - bei Kollision: deterministisch `-2`, `-3`, ...
- `--status` optional; Default ist der **erste** Status in lexikographisch sortierter Projekt-Statusliste.
- `--tags`: CSV, split an `,`, trim je Eintrag, leere Einträge verwerfen.
- `--assignee`: muss String sein.
- `--priority`: nur `P0..P3`.
- `--due-date`: ISO-8601 Date oder DateTime.

### Output (Minimalbeispiel)
```json
{
  "ok": true,
  "project_id": "acme-s4",
  "task_id": "fix_posting_logic",
  "status": "open",
  "title": "fix posting logic"
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
  [--fields f1,f2,...]
  [--limit <int>]
  [--offset <int>]
  [--sort created_at|updated_at|title|priority|due_date]
  [--desc | --asc]
```

### Defaults & Constraints
- `limit` default `100`, muss `>0`, max `1000`.
- `offset` default `0`, muss `>=0`.
- `sort` default `updated_at`.
- Sort-Reihenfolge default `desc=true` (wenn weder `--desc` noch `--asc` gesetzt).
- Zulässige Sort-Felder: `created_at`, `updated_at`, `title`, `priority`, `due_date`.

### Sortierung (normativ)
1. Werte mit vorhandenem Sort-Key (`present`) werden sortiert nach `(sort_value, task_id)`.
2. `--desc`/Default: `present` absteigend; `--asc`: aufsteigend.
3. Werte ohne Sort-Key (`missing`) kommen **immer zuletzt**, intern nach `task_id` aufsteigend.
4. Tie-Breaker ist `task_id`.

`due_date` wird für Sortierung als ISO Date/DateTime geparst; nicht parsebare Werte gelten als `missing`.

### Filter-/Fields-Logik
- Filter sind exakte Matches:
  - `tag`: muss in `tags` enthalten sein
  - `assignee`: exakter Stringmatch
  - `priority`: exakter Stringmatch
- Default-Felder ohne `--fields`:
  - `task_id,status,title,priority,updated_at`
- Bei `--fields`: nur gewünschte Felder, **aber `task_id` und `status` werden immer ergänzt**.

### Output (Minimalbeispiel)
```json
{
  "ok": true,
  "project_id": "acme-s4",
  "count": 2,
  "items": [
    {
      "task_id": "fix_posting_logic",
      "status": "open",
      "title": "fix posting logic",
      "priority": "P2",
      "updated_at": "2026-02-19T15:20:00+00:00"
    }
  ]
}
```

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
- Ohne `--body`: nur Meta.
- `max-body-chars` und `max-body-lines` müssen `>=0` sein (wenn gesetzt).

### Trunkierungsregeln (normativ)
Wenn `--body` aktiv ist und beide Limits gesetzt sind:
1. **zuerst** `max-body-lines`
2. **danach** `max-body-chars`

`body.truncated=true`, sobald mindestens ein Limit gekürzt hat.

### Output (Minimalbeispiel mit Body)
```json
{
  "ok": true,
  "project_id": "acme-s4",
  "task_id": "fix_posting_logic",
  "status": "open",
  "meta": {
    "task_id": "fix_posting_logic",
    "status": "open",
    "created_at": "2026-02-19T15:00:00+00:00",
    "updated_at": "2026-02-19T15:20:00+00:00",
    "title": "fix posting logic"
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

### Verhalten
- Validiert Projekt/Task/Status.
- Schreibt Move-Journal (`.tx_move.json`).
- Verschiebt Body-Datei via `os.replace`.
- Aktualisiert Source-/Target-Index.
- Setzt `status` auf Zielstatus und `updated_at` auf jetzt.

### Fehlerfälle (Auszug)
- Zielstatus ungültig: `VALIDATION_ERROR`.
- Task bereits im Zielstatus: `VALIDATION_ERROR`.
- Body fehlt / inkonsistenter Indexzustand: `INTEGRITY_ERROR`.

### Output (Minimalbeispiel)
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
  (--patch-json '<json>' | --patch-stdin)
```

Genau **eine** Patch-Quelle ist erlaubt.

### Patch-Schema (operativ)
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
- Patch muss JSON-Objekt sein.
- `set` (falls vorhanden) muss Objekt sein.
- `unset` (falls vorhanden) muss Liste sein.
- Nicht patchbar in `set` oder `unset`:
  - `task_id`, `created_at`, `updated_at`, `status`, `title`
- `unset`-Elemente: nur nichtleere Strings.
- Typregeln bei `set`:
  - `tags`: Liste nichtleerer Strings
  - `assignee`: String
  - `priority`: `P0..P3`
  - `due_date`: String, ISO-8601 Date/DateTime
- Löschen erfolgt nur über `unset` (nicht über `null`).

### Output (Minimalbeispiel)
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
  (--text "<body>" | --file /path/to/file.md)
```

### Constraints
- Genau **eine** Quelle (`--text` XOR `--file`).
- Bei `--file`: Datei muss existieren, sonst `NOT_FOUND`.
- Body wird vollständig ersetzt.
- `updated_at` wird aktualisiert.

### Output (Minimalbeispiel)
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

### Verhalten
- Prüft Projektkonsistenz über alle Status.
- Wenn Move-Journal vorhanden: Recovery wird vor Checks versucht (`recovered=true` bei ausgeführter Recovery).
- Mit `--fix`: konservative Reparaturen (Details in `references/architecture.md`).

### Return-Felder
- `ok`: `true`, wenn keine offenen Issues übrig sind.
- `recovered`: `true`, wenn Journal-Recovery lief.
- `fixed`: Liste tatsächlich ausgeführter Reparaturen.
- `issues`: offene (nicht behobene) Probleme.
- `found`: alle Findings (inkl. der bereits behobenen).

### Output (Minimalbeispiel)
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
