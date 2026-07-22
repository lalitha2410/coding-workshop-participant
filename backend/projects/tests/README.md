# Projects service — tests

Two layers, following the workshop testing guidance:

- **`test_validation.py`** — unit tests for payload validation (pure, no DB).
- **`test_handler.py`** — unit tests for the `function.handler` router with the
  repository monkeypatched; covers routing, status codes (200/201/204/400/404/405/500),
  request parsing (API Gateway v1 + v2 shapes), and JSON serialization.
- **`test_integration.py`** — round-trips create → read → list/filter → update →
  delete against a **real local PostgreSQL**. Auto-skips when the DB or `projects`
  table is unavailable, and cleans up every row it creates.

## Setup

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/projects/requirements-dev.txt
```

## Run

```sh
# Unit tests only (no database needed)
pytest backend/projects/tests/test_validation.py backend/projects/tests/test_handler.py

# Everything, including integration against local Postgres
# (defaults: localhost:5432, postgres/postgres, dbname projectdb, schema loaded)
IS_LOCAL=true pytest backend/projects/tests/
```

Integration tests read the same `POSTGRES_*` env vars as the service. Set
`IS_LOCAL=true` locally so the connection skips `sslmode=require`.
