# Deliverables service — tests

Same structure as the projects service tests:

- **`test_validation.py`** — unit tests for payload validation (pure, no DB):
  required `project_id`/`name`, status enum, `completion_pct` 0–100, date format.
- **`test_handler.py`** — unit tests for the `function.handler` router with the
  repository (including the `project_exists` reference check) monkeypatched.
  Covers routing, status codes (200/201/204/400/404/405/500), the missing-parent
  reference guard, request parsing (API Gateway v1 + v2), and JSON serialization.
- **`test_integration.py`** — round-trips create → read → list/filter → update →
  delete against a **real local PostgreSQL**, plus the FK reference behavior.
  Creates a throwaway parent project (deleted via `ON DELETE CASCADE`), and
  auto-skips when the DB or `deliverables` table is unavailable.

## Run

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/deliverables/requirements-dev.txt

# Unit tests only (no database needed)
pytest backend/deliverables/tests/test_validation.py backend/deliverables/tests/test_handler.py

# Everything, including integration against local Postgres
IS_LOCAL=true pytest backend/deliverables/tests/
```
