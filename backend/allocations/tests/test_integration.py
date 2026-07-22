"""
Integration tests for the allocations service against a real local PostgreSQL.

These hit the database defined by the POSTGRES_* env vars (defaults:
localhost:5432, postgres/postgres, projectdb) and run through the repository
layer. Throwaway parent projects and resources are created for the allocations
to reference; deleting them cascades to the allocations (ON DELETE CASCADE), so
cleanup is guaranteed. The whole module auto-skips when the DB/schema is absent.

Run against the local dev database with the schema loaded:
    IS_LOCAL=true pytest backend/allocations/tests/test_integration.py
"""

import pytest

import postgres_service
from allocations_repository import (
    list_allocations,
    get_allocation,
    create_allocation,
    update_allocation,
    delete_allocation,
    resource_exists,
    project_exists,
    resource_allocation_totals,
    DuplicateAllocationError,
)


def _database_ready():
    try:
        postgres_service.execute("SELECT 1 FROM allocations LIMIT 1", fetch="one")
        return True
    except Exception:
        postgres_service.PG_CONN = None
        return False


pytestmark = pytest.mark.skipif(
    not _database_ready(),
    reason="local PostgreSQL with the allocations schema is not available",
)


def _mk_project(name):
    row = postgres_service.execute(
        "INSERT INTO projects (name, status) VALUES (%s, 'planning') RETURNING id",
        (name,), fetch="one",
    )
    return row["id"]


def _mk_resource(name, email):
    row = postgres_service.execute(
        "INSERT INTO resources (name, email) VALUES (%s, %s) RETURNING id",
        (name, email), fetch="one",
    )
    return row["id"]


@pytest.fixture
def env():
    """Two projects and two resources; teardown cascades to their allocations."""
    p1 = _mk_project("Alloc IT Project 1")
    p2 = _mk_project("Alloc IT Project 2")
    r1 = _mk_resource("Alloc IT R1", "alloc-it-r1@example-test.invalid")
    r2 = _mk_resource("Alloc IT R2", "alloc-it-r2@example-test.invalid")
    yield {"p1": p1, "p2": p2, "r1": r1, "r2": r2}
    for pid in (p1, p2):
        postgres_service.execute("DELETE FROM projects WHERE id = %s", (pid,))
    for rid in (r1, r2):
        postgres_service.execute("DELETE FROM resources WHERE id = %s", (rid,))


# ---------------------------------------------------------------------------
# Reference-existence helpers
# ---------------------------------------------------------------------------

def test_reference_helpers(env):
    assert resource_exists(env["r1"]) is True
    assert project_exists(env["p1"]) is True
    assert resource_exists(2_000_000_000) is False
    assert project_exists(2_000_000_000) is False


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def test_create_persists_and_default_pct(env):
    a = create_allocation({"resource_id": env["r1"], "project_id": env["p1"]})
    assert a["id"] is not None
    assert a["resource_id"] == env["r1"]
    assert a["allocation_pct"] == 0  # COALESCE default


def test_get_and_missing(env):
    a = create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 30})
    assert get_allocation(a["id"])["allocation_pct"] == 30
    assert get_allocation(2_000_000_000) is None


def test_list_filters(env):
    a1 = create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 10})
    a2 = create_allocation({"resource_id": env["r1"], "project_id": env["p2"], "allocation_pct": 20})
    a3 = create_allocation({"resource_id": env["r2"], "project_id": env["p1"], "allocation_pct": 30})

    by_resource = list_allocations(resource_id=env["r1"])
    ids = {a["id"] for a in by_resource}
    assert a1["id"] in ids and a2["id"] in ids and a3["id"] not in ids

    by_project = list_allocations(project_id=env["p1"])
    ids = {a["id"] for a in by_project}
    assert a1["id"] in ids and a3["id"] in ids and a2["id"] not in ids

    both = list_allocations(resource_id=env["r1"], project_id=env["p2"])
    assert [a["id"] for a in both] == [a2["id"]]


def test_partial_update_preserves_other_fields(env):
    a = create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 40})
    updated = update_allocation(a["id"], {"allocation_pct": 80})
    assert updated["allocation_pct"] == 80
    assert updated["resource_id"] == env["r1"]
    assert updated["project_id"] == env["p1"]


def test_update_missing_returns_none():
    assert update_allocation(2_000_000_000, {"allocation_pct": 10}) is None


def test_delete_removes_row(env):
    a = create_allocation({"resource_id": env["r2"], "project_id": env["p2"], "allocation_pct": 5})
    assert delete_allocation(a["id"])["id"] == a["id"]
    assert get_allocation(a["id"]) is None
    assert delete_allocation(a["id"]) is None


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

def test_duplicate_pair_raises(env):
    create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 10})
    with pytest.raises(DuplicateAllocationError):
        create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 20})
    # Connection stays usable after the constraint violation (execute rolls back).
    assert list_allocations(resource_id=env["r1"]) != []


def test_missing_fk_raises_foreign_key_violation(env):
    import psycopg
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        create_allocation({"resource_id": 2_000_000_000, "project_id": env["p1"]})
    postgres_service.PG_CONN = None  # reset connection soured by the failed tx


# ---------------------------------------------------------------------------
# Over-allocation business logic
# ---------------------------------------------------------------------------

def test_over_allocation_calculation(env):
    # r1 allocated 60% + 60% across two projects => 120% (over-allocated).
    create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 60})
    create_allocation({"resource_id": env["r1"], "project_id": env["p2"], "allocation_pct": 60})
    # r2 allocated 50% on one project => not over-allocated.
    create_allocation({"resource_id": env["r2"], "project_id": env["p1"], "allocation_pct": 50})

    over = resource_allocation_totals(over_only=True)
    over_by_id = {row["resource_id"]: row for row in over}
    assert env["r1"] in over_by_id
    assert over_by_id[env["r1"]]["total_allocation_pct"] == 120
    assert over_by_id[env["r1"]]["project_count"] == 2
    assert over_by_id[env["r1"]]["over_allocated"] is True
    # r2 is under 100% and must NOT appear in the over-allocated view.
    assert env["r2"] not in over_by_id

    summary = resource_allocation_totals(over_only=False)
    summary_by_id = {row["resource_id"]: row for row in summary}
    assert summary_by_id[env["r1"]]["over_allocated"] is True
    assert summary_by_id[env["r2"]]["total_allocation_pct"] == 50
    assert summary_by_id[env["r2"]]["over_allocated"] is False


def test_exactly_100_is_not_over_allocated(env):
    create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 100})
    over_ids = {row["resource_id"] for row in resource_allocation_totals(over_only=True)}
    assert env["r1"] not in over_ids  # 100% is fully allocated, not OVER


def test_summary_includes_unallocated_resource(env):
    # Allocate r1 but leave r2 with no allocations at all.
    create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 30})

    summary = {row["resource_id"]: row for row in resource_allocation_totals(over_only=False)}
    # LEFT JOIN: the unallocated resource still appears, at 0%.
    assert env["r2"] in summary, "unallocated resource should appear in /summary (LEFT JOIN)"
    assert summary[env["r2"]]["total_allocation_pct"] == 0
    assert summary[env["r2"]]["project_count"] == 0
    assert summary[env["r2"]]["over_allocated"] is False

    # But it must NOT appear in the over-allocated (INNER JOIN) view.
    over_ids = {row["resource_id"] for row in resource_allocation_totals(over_only=True)}
    assert env["r2"] not in over_ids
