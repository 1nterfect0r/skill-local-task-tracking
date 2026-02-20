# Task-Tracking (Option 1, v1) – Ziel, Scope, Konzept (Entwickler)

> Architektur-/Scope-Referenz für den registrierten Skill `task-tracking` (Implementierung unter `scripts/`).

## 0. Ziel & Scope (v1)
**Ziel:** Ein lokales, dateisystembasiertes Task‑Tracking für mehrere Projekte. Alle Mutationen laufen deterministisch über eine Python‑CLI. **Kein Netzwerkzugriff.**

**In Scope (v1):**
- Projekt initialisieren
- Task anlegen
- Tasks listen (filterbar, limitiert)
- Task anzeigen (Meta standardmäßig; Body opt‑in, begrenzt)
- Task in anderen Status verschieben (atomar)
- Metadaten aktualisieren (robust, patch‑orientiert)
- Body setzen/ersetzen (Text oder Datei)

**Out of Scope (v1):**
- Delete/Archive
- Remote/SaaS‑Integrationen, Sync, Notifications, Kalender
- Automatische Statusübergänge
- Reporting/Exports
- Human‑Output (Tabellen o. ä.) – **v1 liefert nur JSON auf stdout**

## 1. Terminologie
- **Project:** Sammlung von Tasks unter `project_id`.
- **Status:** Zustand eines Tasks (konfiguriertes Set; Default z. B. `backlog`, `open`, `done`).
- **Task:** besteht aus **Body** (`{task_id}.md`) und **Metadata** (Eintrag in `index.json` des jeweiligen Status‑Ordners).

## 2. Konfiguration & Pfadregeln
- **Root (OpenClaw empfohlen):** `TASK_TRACKING_ROOT=.task-tracking` (relativ zum Workspace-CWD, effektiv `<workspace>/.task-tracking`).
- **Fallback der CLI:** falls `TASK_TRACKING_ROOT` nicht gesetzt ist, `${CWD}/.task_tracking`.
- **Sicherheitsregel:** Niemals außerhalb des Roots lesen/schreiben (Path‑Traversal verhindern).
- **Identifikatoren:** `project_id` und `task_id` müssen `^[A-Za-z0-9_-]+$` matchen. Keine Separatoren, kein `..`, keine Leerzeichen.
  - Anzeige: `_` darf zu Space gemappt werden; intern bleibt die ID unverändert.
- **Statusnamen:** ebenfalls `^[A-Za-z0-9_-]+$`.
  - v1 Default‑Statusliste beim Init (z. B. `backlog,open,done`).
  - Statusliste wird **immer** aus den vorhandenen Statusordnern abgeleitet.

## 3. Kanonisches Layout (Kurzüberblick)
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
**Regel:** pro Statusordner existiert genau **ein** `index.json`, das alle Metadaten in diesem Status hält.

## 4. Nichtfunktionale Anforderungen
- **Portabilität:** Python 3.10+, Windows/Linux/macOS.
- **Determinismus:** stabile JSON‑Strukturen, stabile Sortierlogik.
- **Performance:** `list` muss über Statusfilter/Limit steuerbar bleiben.
- **Fehlerrobustheit:** Validierungsfehler liefern strukturierte JSON‑Fehlerobjekte; keine Stacktraces in stdout.

Weiteres Detail: siehe `filesystem_layout.md`, `metadata_schema.md`, `cli_reference.md`, `architecture.md`.
