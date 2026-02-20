# Metadaten-Schema (Single Source of Truth, v1)

## Inhaltsverzeichnis
- [1) Persistentes Datenmodell](#1-persistentes-datenmodell)
- [2) Task-Metadaten (`meta`)](#2-task-metadaten-meta)
  - [2.1 Required Fields](#21-required-fields)
  - [2.2 Optionale Standardfelder](#22-optionale-standardfelder)
  - [2.3 Weitere benutzerdefinierte Felder](#23-weitere-benutzerdefinierte-felder)
- [3) Nicht patchbare Felder](#3-nicht-patchbare-felder)
- [4) Patch-Schema für `meta-update`](#4-patch-schema-für-meta-update)
  - [4.1 Formales Patch-Format](#41-formales-patch-format)
  - [4.2 Validierungsregeln](#42-validierungsregeln)
- [5) Tags-Regeln und Normalisierung](#5-tags-regeln-und-normalisierung)
- [6) Body-Datei-Schema](#6-body-datei-schema)

## 1) Persistentes Datenmodell

### 1.1 Index-Datei je Status
Jeder Statusordner enthält eine `index.json` mit diesem Top-Level-Format:

```json
{
  "<task_id>": { "...meta...": "..." }
}
```

- Top-Level ist immer ein JSON-Objekt.
- Key ist `task_id`.
- Value ist das Metadatenobjekt der Task.

### 1.2 Title ist abgeleitet, nicht persistent
- `title` wird **nirgends gespeichert**.
- `title` wird bei I/O aus `task_id` gebildet (`_` → Leerzeichen).

---

## 2) Task-Metadaten (`meta`)

## 2.1 Required Fields
Diese Felder müssen in `meta` vorhanden sein:

| Feld | Typ | Bedeutung |
|---|---|---|
| `task_id` | string | Kanonische Task-ID (muss zum Index-Key passen) |
| `status` | string | Aktueller Status (muss zum Statusordner passen) |
| `created_at` | string | ISO-8601 Timestamp |
| `updated_at` | string | ISO-8601 Timestamp |

### 2.1.1 Zeitstempel-Semantik
- `created_at`: wird bei Erstellung gesetzt.
- `updated_at`: wird bei jeder Mutation aktualisiert (`add`, `move`, `meta-update`, `set-body`).

## 2.2 Optionale Standardfelder

| Feld | Typ | Validierung |
|---|---|---|
| `tags` | array[string] | Jedes Element String und nicht leer (nach `strip`) |
| `assignee` | string | Muss String sein |
| `priority` | string | Nur `P0`, `P1`, `P2`, `P3` |
| `due_date` | string | ISO-8601 Date oder DateTime |

Hinweis: `null` ist für die obigen typisierten Felder kein gültiger Wert im `set`-Pfad.

## 2.3 Weitere benutzerdefinierte Felder
`meta-update` erlaubt zusätzliche (nicht reservierte) Felder via `set`.

- Reservierte Felder siehe Abschnitt 3.
- Für zusätzliche Felder gibt es derzeit keine strikte Typvalidierung im Code (außer den bekannten Feldern oben).

---

## 3) Nicht patchbare Felder

Diese Felder dürfen **weder** in `set` **noch** in `unset` verändert werden:

- `task_id`
- `created_at`
- `updated_at`
- `status`
- `title`

Begründung:
- `status` wird nur über `move` geändert.
- `title` ist abgeleitet, nicht gespeichert.
- Kernidentität/-historie (`task_id`, `created_at`, `updated_at`) bleibt geschützt.

---

## 4) Patch-Schema für `meta-update`

## 4.1 Formales Patch-Format

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

### 4.1.1 Strukturregeln
- Patch selbst: JSON-Objekt.
- `set` optional; falls vorhanden: JSON-Objekt.
- `unset` optional; falls vorhanden: JSON-Liste.
- Weitere Top-Level-Keys sind aktuell ohne Wirkung (werden ignoriert).

## 4.2 Validierungsregeln

### 4.2.1 `set`
- Key darf nicht reserviert sein (siehe Abschnitt 3).
- Feldspezifische Regeln:
  - `tags`: muss Liste sein; jedes Element String und nicht leer nach `strip`.
  - `assignee`: muss String sein.
  - `priority`: muss `P0|P1|P2|P3` sein.
  - `due_date`: muss String sein und ISO-8601 Date/DateTime parsebar sein.
- Für andere Keys gilt derzeit keine zusätzliche Typrestriktion.

### 4.2.2 `unset`
- Muss Liste aus nichtleeren Strings sein.
- Jeder Eintrag darf nicht reserviert sein.
- Entfernt den Key, wenn vorhanden.

### 4.2.3 Delete-Semantik
- `null` in `set` ist **kein** Delete-Mechanismus.
- Löschen erfolgt ausschließlich über `unset`.

---

## 5) Tags-Regeln und Normalisierung

## 5.1 Beim `add`-Command
`--tags "a,b,c"` wird normalisiert:
1. Split an `,`
2. Trim je Tag
3. Leere Tags werden verworfen

Beispiel:
- Input: `" sap, fi , ,co "`
- Persistiert: `["sap", "fi", "co"]`

## 5.2 Beim `meta-update`-Command
`set.tags` erwartet bereits eine Liste.

- Keine CSV-Splittung.
- Elemente müssen Strings sein und dürfen nicht nur aus Whitespace bestehen.
- Bestehende Inhalte werden nicht automatisch getrimmt/normalisiert.

---

## 6) Body-Datei-Schema

- Body liegt als `<task_id>.md` im jeweiligen Statusordner.
- Inhalt ist UTF-8 Text (Markdown-konventionell, aber nicht strikt validiert).
- Body ist nicht Teil von `index.json`.
