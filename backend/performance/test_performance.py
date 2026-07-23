"""
Performance suite — practical signal, not a framework.

What's measured and why:

  * Response time of the hot repository operations (list / get / create) for a
    representative entity, so a change that makes them an order of magnitude
    slower (an N+1, a dropped index, an accidental full scan) trips the build.

  * List latency against a larger table (a few hundred seeded rows), which
    exercises the indexes added in schema.sql — a filtered/searched list must
    stay fast rather than degrade into a sequential scan.

  * A light concurrency check: N workers, each with its OWN connection (the way
    N warm Lambda containers each reuse their own module-level connection), hit
    the database at once and must all succeed — verifying the connection pattern
    holds up under simultaneous load.

Thresholds are deliberately generous — observed local medians are well under
1ms, so these ceilings sit ~50-150x above baseline. They are not micro-benchmarks;
they exist to catch gross, order-of-magnitude regressions without flaking on a
loaded CI machine. Run with `-s` to print the actual medians.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest

import testkit

pytestmark = [
    pytest.mark.performance,
    pytest.mark.skipif(
        not testkit.database_ready("projects"),
        reason="performance suite needs a local PostgreSQL with the schema loaded",
    ),
]

# Ceilings in milliseconds (median over many runs). See the module docstring.
LIST_MS = 60
GET_MS = 40
CREATE_MS = 120
SCALED_LIST_MS = 80
SCALED_SEARCH_MS = 80

CONCURRENCY_WORKERS = 20


# ---------------------------------------------------------------------------
# Response-time benchmarks for the hot operations
# ---------------------------------------------------------------------------

def test_list_response_time_under_threshold(timer):
    from projects_repository import list_projects

    def op():
        list_projects(limit=50)
    op.__label__ = "list(limit=50)"
    assert timer(op) < LIST_MS


def test_get_response_time_under_threshold(timer):
    from projects_repository import create_project, get_project, delete_project

    row = create_project({"name": "perf-get", "department": "PERF-PROBE"})
    try:
        def op():
            get_project(row["id"])
        op.__label__ = "get_by_id"
        assert timer(op) < GET_MS
    finally:
        delete_project(row["id"])


def test_create_response_time_under_threshold(timer):
    from projects_repository import create_project, delete_project

    def op():
        rid = create_project({"name": "perf-create", "department": "PERF-PROBE"})["id"]
        delete_project(rid)
    op.__label__ = "create+delete"
    assert timer(op) < CREATE_MS


# ---------------------------------------------------------------------------
# Scaling: list stays fast with a larger dataset (indexes earn their keep)
# ---------------------------------------------------------------------------

def test_filtered_list_stays_fast_on_larger_dataset(timer, seeded_projects):
    list_projects = seeded_projects["list_projects"]
    tag = seeded_projects["tag"]
    # Sanity: the rows are really there.
    assert list_projects(department=tag, limit=1)["total"] >= seeded_projects["count"]

    def op():
        list_projects(department=tag, limit=50)
    op.__label__ = f"list(department) over {seeded_projects['count']}+ rows"
    assert timer(op) < SCALED_LIST_MS


def test_search_stays_fast_on_larger_dataset(timer, seeded_projects):
    list_projects = seeded_projects["list_projects"]

    def op():
        list_projects(search="perf-seed-250", limit=50)
    op.__label__ = f"search over {seeded_projects['count']}+ rows"
    assert timer(op) < SCALED_SEARCH_MS


# ---------------------------------------------------------------------------
# Concurrency: N independent connections hit the DB at once, all succeed
# ---------------------------------------------------------------------------

def test_concurrent_reads_all_succeed():
    """Simulate N warm containers (each its own connection) querying together."""
    import postgres_service
    from psycopg import connect
    from psycopg.rows import dict_row

    def worker(_):
        # A fresh connection per worker — the module-level pooled connection is
        # per-process/per-container and not shared across threads.
        conn = connect(postgres_service.PG_CONFIG, row_factory=dict_row)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM projects")
                return cur.fetchone()["n"]
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=CONCURRENCY_WORKERS) as pool:
        results = list(pool.map(worker, range(CONCURRENCY_WORKERS)))

    # Every worker completed without error and saw a consistent row count.
    assert len(results) == CONCURRENCY_WORKERS
    assert all(isinstance(n, int) for n in results)
    assert len(set(results)) == 1
