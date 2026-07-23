# Backend tests

Every service (`auth`, `projects`, `deliverables`, `resources`, `allocations`)
is tested with the **same four-file structure**, so once you know one suite you
know them all. Tests are classified by *type* — both in the file name and in a
pytest marker — so you can run any subset.

## Structure

Inside each `backend/<service>/tests/`:

| File | Marker | What it covers |
|------|--------|----------------|
| `test_unit.py` | `unit` | Pure logic, **no database** — validation rules, `parse_search`, the shared `activity` helpers. |
| `test_api.py` | `api` | `function.handler` routing, status codes, request parsing, pagination plumbing, response shaping. The repository is mocked (shared `repo` fixture). |
| `test_security.py` | `security` | Authentication, the RBAC gate (per-role 401/403), token handling, and SQL-injection resistance. |
| `test_integration.py` | `integration` | Real database round-trips through the repository layer, plus the activity log written end-to-end through the handler. Auto-skips when no DB is available. |

The **performance** suite lives on its own at `backend/performance/` (marker
`performance`) and is opt-in — see below.

### Shared scaffolding (no per-service duplication)

- `backend/pytest.ini` — registers the markers (with `--strict-markers`).
- `backend/conftest.py` — the shared `repo` (repository stub recorder) and
  `admin_auth` (Admin-token injection) fixtures.
- `backend/testkit.py` — `parse_body`, `make_event`, `bearer`, `database_ready`,
  `make_repo_stub`.

Each service's `tests/conftest.py` is now three things: put the service dir +
backend dir on `sys.path`, and (for the CRUD services) an autouse one-liner that
opts its handler tests into `admin_auth`. `auth` manages its own tokens, so it
omits the autouse stub and instead shares a `bypass_user_check` fixture.

## Running

```sh
# Everything, every service (unit + api + security + integration)
bin/test.sh

# One type across all services
bin/test.sh -m unit
bin/test.sh -m security
bin/test.sh -m "not integration"      # skip DB tests (runs anywhere)

# A single service (full, or one type)
bin/test.sh projects
bin/test.sh projects -m api

# The opt-in performance suite (DB-backed; prints timings with -s)
bin/test.sh performance
bin/test.sh performance -s
```

Or call pytest directly from a service directory (the shared `pytest.ini` is
discovered automatically):

```sh
cd backend/projects && POSTGRES_NAME=projectdb python3 -m pytest -m unit
```

### Database

`integration` and `performance` tests need a local PostgreSQL with the schema
loaded. They read the standard `POSTGRES_*` env vars; `bin/test.sh` defaults to
`POSTGRES_NAME=projectdb` and `IS_LOCAL=true` (skips `sslmode=require`). When the
DB or a required table is missing, those tests **skip** cleanly so the
`unit`/`api`/`security` suites still run anywhere.

## Category parity

All five services now carry all four categories. One gap was found and closed
during the reorg: `auth` previously had **no pure `unit` tests** — its input
validation was only exercised through the handler. A `test_unit.py` covering the
`validation` module directly was added.

## Performance suite

See the module docstring in `backend/performance/test_performance.py` for exactly
what is measured and why the thresholds were chosen. In short: response-time
ceilings for the hot repository ops (list/get/create), a list-stays-fast check on
a few hundred seeded rows (exercises the indexes), and a concurrency check where
N workers each open their own connection (as N warm Lambda containers would) and
must all succeed. Thresholds sit well above observed local medians (< 1 ms) so
they catch order-of-magnitude regressions without flaking.
