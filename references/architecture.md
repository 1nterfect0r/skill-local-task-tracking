# Architektur: Integrität, Recovery, Journaling (v1)

## Inhaltsverzeichnis
- [1) Datenlayout und Zuständigkeiten](#1-datenlayout-und-zuständigkeiten)
- [2) Locking-Modell](#2-locking-modell)
- [3) Move-Journaling und Recovery](#3-move-journaling-und-recovery)
- [4) `integrity-check`: Ablauf und Datenmodell](#4-integrity-check-ablauf-und-datenmodell)
- [5) Bedeutung von `--fix` (konservative Repairs)](#5-bedeutung-von---fix-konservative-repairs)
- [6) Duplicate Resolution (Regel + Fallback)](#6-duplicate-resolution-regel--fallback)
- [7) Rückgabefelder (`ok`, `recovered`, `fixed`, `issues`, `found`)](#7-rückgabefelder-ok-recovered-fixed-issues-found)

## 1) Datenlayout und Zuständigkeiten

Pro Projekt:
- `<project>/<status>/index.json` (Task-Metadaten je Status)
- `<project>/<status>/<task_id>.md` (Body-Datei)
- `<project>/.lock` (exklusiver Projekt-Lock)
- `<project>/.tx_move.json` (Move-Transaktionsjournal)

Module:
- `service.py`: Domänenlogik, Integritätsprüfung, Recovery.
- `storage.py`: atomare Writes, Locking, Root-Schutz.
- `validators.py`: Input-/Schema-Validierung.

---

## 2) Locking-Modell

`ProjectLock` nutzt ein exklusives Lockfile (`O_CREAT|O_EXCL`).

- Aktiver Lock → `CONFLICT` (Exit 4), `details.reason = "LOCKED"`.
- Stale Lock (PID nicht mehr aktiv) wird best-effort entfernt und neu übernommen.
- Schlägt stale-Recovery fehl, bleibt es bei `CONFLICT`.

Wesentlich: mutierende Operationen arbeiten unter Lock; so werden konkurrierende Writer verhindert.

---

## 3) Move-Journaling und Recovery

## 3.1 Journal-Datei
Vor einem `move` schreibt der Service `.tx_move.json` mit:
- `op: "move"`
- `task_id`
- `from`
- `to`
- `updated_meta` (geplante Ziel-Metadaten)

## 3.2 Warum Journal?
Bei Crash/Abbruch zwischen Body-Move und Index-Update könnte ein Teilzustand entstehen.
Das Journal macht diesen Zustand deterministisch recoverbar.

## 3.3 Recovery-Trigger
Recovery läuft, wenn `.tx_move.json` existiert:
- vor Integritäts-Operationen,
- über `integrity-check`,
- sowie in anderen Workflows, die Integrität sicherstellen.

## 3.4 Recovery-Logik (vereinfacht)
1. Journal validieren (`op`, Felder, IDs/Status).
2. Quell-/Zielindex und Body-Existenz prüfen.
3. Konsistente Endzustände erkennen:
   - bereits vollständig Quelle **oder** vollständig Ziel → Journal löschen.
4. Inkonsistente Zwischenzustände reparieren:
   - wenn Body bereits im Ziel: Quellindex bereinigen, Zielindex finalisieren.
   - wenn Body noch in Quelle: Body verschieben, Indizes finalisieren.
5. Bei unauflösbarem Zustand: `INTEGRITY_ERROR`.

---

## 4) `integrity-check`: Ablauf und Datenmodell

## 4.1 Ablauf (ohne `--fix`)
1. Projektstatus-Verzeichnisse laden.
2. Indizes je Status lesen.
3. Findings sammeln (`found`).
4. Nicht behobene Findings in `issues` aufnehmen.
5. `ok = (len(issues) == 0)`.

## 4.2 Ablauf (mit `--fix`)
Zusätzlich zu oben:
- konservative Reparaturen durchführen,
- Reparaturaktionen in `fixed` protokollieren,
- verbleibende Probleme weiterhin in `issues` belassen.

## 4.3 Interne Check-Klassen (aus Code)
Typische `found`/`issues`-Typen:
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

## 5) Bedeutung von `--fix` (konservative Repairs)

`--fix` repariert nur klar ableitbare, risikoarme Fälle:

1. **Fehlende Index-Datei** (`INDEX_ERROR` + missing file)
   - erstellt leeren Index.
   - `fixed`: `INDEX_CREATED`.

2. **Meta ist kein Objekt** (`META_NOT_OBJECT`)
   - ersetzt durch Minimal-Meta (`task_id`, `status`, `created_at`, `updated_at`).
   - `fixed`: `META_REPLACED`.

3. **Pflichtfelder fehlen** (`MISSING_FIELD`)
   - ergänzt fehlende Felder:
     - `task_id` = Index-Key,
     - `status` = Statusordner,
     - `created_at`/`updated_at` = `now`.
   - `fixed`: `FIELD_FILLED`.

4. **`meta.task_id` oder `meta.status` inkonsistent**
   - korrigiert auf kanonische Werte.
   - `fixed`: `TASK_ID_FIXED`, `STATUS_FIXED`.

5. **Leere/fehlende Body-Datei** (`MISSING_BODY`)
   - erzeugt leere `<task_id>.md`.
   - `fixed`: `BODY_CREATED`.

6. **Orphan Body** (`ORPHAN_BODY`)
   - erzeugt Indexeintrag nur dann, wenn `task_id` nicht bereits in einem anderen Status existiert.
   - `fixed`: `ORPHAN_INDEX_CREATED`.

7. **Duplikate über Status** (`DUPLICATE_TASK`)
   - wählt Winner (siehe Abschnitt 6), entfernt andere Indexeinträge.
   - `fixed`: `DUPLICATE_RESOLVED`.
   - falls Winner-Body fehlt und ein loser Duplicate-Body existiert:
     - Body wird zum Winner verschoben.
     - `fixed`: `BODY_MOVED_FROM_DUPLICATE`.

Nicht eindeutig behebbare Fälle bleiben in `issues`.

---

## 6) Duplicate Resolution (Regel + Fallback)

Wenn eine `task_id` in mehreren Statusindizes vorkommt:

1. Primärregel: **neuester `updated_at` gewinnt**.
2. Falls kein parsebares `updated_at` verfügbar:
   - Fallback: **Statusreihenfolge des Projekts** (lexikographisch sortierte Statusnamen; erster Treffer gewinnt).
3. Letzter Fallback: erste gefundene Statuszuordnung.

Diese Regeln sind deterministisch und reproduzierbar.

---

## 7) Rückgabefelder (`ok`, `recovered`, `fixed`, `issues`, `found`)

`integrity-check` liefert immer:

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

Semantik:
- `found`: alle gefundenen Probleme (unabhängig davon, ob behoben).
- `fixed`: nur tatsächlich durchgeführte Reparaturen.
- `issues`: verbleibende, offene Probleme nach optionalem Fix.
- `recovered`: `true`, wenn Move-Journal-Recovery in diesem Lauf ausgeführt wurde.
- `ok`: genau dann `true`, wenn `issues` leer ist; sonst `false`.
