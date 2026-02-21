# Test log — Task‑Tracking

Single current test snapshot (older snapshots intentionally removed; see Git history for prior runs).

## Latest run
- Time (UTC): 2026-02-21T10:28:44Z
- Runner: `references/test_runner.sh`
- Result: **successful** (`pass=36`, `fail=0`)
- Log artifact: `/home/hanneskuhl/.openclaw/workspace/tmp/tt-test-2026-02-21T102844Z.log`

## Highlights covered
- Core flow: init/add/list/show/move/meta-update/set-body/integrity-check
- Regression checks: validation, sort behavior, field constraints
- List pagination semantics: `count` (page size) + `count_total` (pre-pagination matches)
- Filter mode extension:
  - `list --filter-mode and`
  - `list --filter-mode or`
  - default filter mode (`and`)
  - invalid `--filter-mode` → `VALIDATION_ERROR`
- Hardening checks for malformed metadata:
  - `due_date` invalid string and non-string (e.g., numeric) do not crash sorting
  - malformed `tags` (non-list) do not crash tag filtering (`and`/`or`)
  - `integrity-check --fix` normalizes/removes invalid known fields (`tags`, `assignee`, `priority`, `due_date`, invalid timestamp types)
- Edge cases 18.x suite
