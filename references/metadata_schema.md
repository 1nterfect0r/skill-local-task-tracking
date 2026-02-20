# Metadata schema (Single Source of Truth, v1)

## Table of contents
- [1) Persistent data model](#1-persistent-data-model)
- [2) Task metadata (`meta`)](#2-task-metadata-meta)
  - [2.1 Required fields](#21-required-fields)
  - [2.2 Optional standard fields](#22-optional-standard-fields)
  - [2.3 Additional custom fields](#23-more-custom-fields)
- [3) Unpatchable fields](#3-unpatchable-fields)
- [4) Patch scheme for `meta-update`](#4-patch-scheme-for-meta-update)
  - [4.1 Formal patch format](#41-formal-patch-format)
  - [4.2 Validation rules](#42-validation-rules)
- [5) Tags rules and normalization](#5-tags-rules-and-normalization)
- [6) Body file schema](#6-body-file-schema)

## 1) Persistent data model

### 1.1 Index file per status
Each status folder contains a `index.json` with this top-level format:

```json
{
  "<task_id>": { "...meta...": "..." }
}
```

- Top level is always a JSON object.
- Key is `task_id`.
- Value is the metadata object of the task.

### 1.2 Derived fields (`title`, `status`) are not persistent
- `title` is **not saved anywhere**.
- `status` is **not saved in metadata**; it is derived from the folder containing the task.
- `title` is formed from `task_id` during I/O (`_` → space).

---

## 2) Task metadata (`meta`)

## 2.1 Required fields
These fields must be present in `meta`:

| Field | Type | Meaning |
|---|---|---|
| `task_id` | string | Canonical task ID (must match the index key) |
| `created_at` | string | ISO-8601 Timestamp |
| `updated_at` | string | ISO-8601 Timestamp |

### 2.1.1 Timestamp semantics
- `created_at`: is set upon creation.
- `updated_at`: updated with every mutation (`add`, `move`, `meta-update`, `set-body`).

## 2.2 Optional standard fields

| Field | Type | Validation |
|---|---|---|
| `tags` | array[string] | Each element must be a string and not empty (after `strip`) |
| `assignee` | string | Must be a string |
| `priority` | string | Only `P0`, `P1`, `P2`, `P3` |
| `due_date` | string | ISO-8601 Date or DateTime |

Note: `null` is not a valid value in the `set` path for the above typed fields.

## 2.3 Other custom fields
`meta-update` allows additional (unreserved) fields via `set`.

- For reserved fields see section 3.
- There is currently no strict type validation in the code for additional fields (other than the well-known fields above).

---

## 3) Non-patchable fields

These fields must not be changed in either `set` or `unset`:

- `task_id`
- `created_at`
- `updated_at`
- `status`
- `title`

Reason:
- `status` is derived from the status folder and is not stored in metadata.
- `title` is derived from `task_id` and is not stored.
- Core identity/history (`task_id`, `created_at`, `updated_at`) remains protected.

---

## 4) Patch scheme for `meta-update`

## 4.1 Formal patch format

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

### 4.1.1 Structural rules
- Patch itself: JSON object.
- `set` optional; if present: JSON object.
- `unset` optional; if present: JSON list.
- Other top-level keys currently have no effect (are ignored).

## 4.2 Validation rules

### 4.2.1 `set`
- Key must not be reserved (see section 3).
- Field-specific rules:
  - `tags`: must be list; every element string and not empty after `strip`.
  - `assignee`: must be string.
  - `priority`: must be `P0|P1|P2|P3`.
  - `due_date`: must be a string and ISO-8601 Date/DateTime must be parseable.
- There are currently no additional type restrictions for other keys.

### 4.2.2 `unset`
- Must be a list of non-empty strings.
- Each entry cannot be reserved.
- Removes the key if it exists.

### 4.2.3 Delete semantics
- `null` in `set` is **not** a delete mechanism.
- Deletion is performed only via `unset`.

---

## 5) Tags rules and normalization

## 5.1 For the `add` command
`--tags "a,b,c"` is normalized:
1. Split on `,`
2. Trim each tag
3. Empty tags are discarded

Example:
- Input: `" sap, fi , ,co "`
- Persists: `["sap", "fi", "co"]`

## 5.2 For the `meta-update` command
`set.tags` expects a list.

- No CSV splitting.
- Elements must be strings and not just whitespace.
- Existing content is not automatically trimmed/normalized.

---

## 6) Body file schema

- Body is located as `<task_id>.md` in the respective status folder.
- Content is UTF-8 text (Markdown conventional but not strictly validated).
- Body is not part of `index.json`.
