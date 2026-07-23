"""
Integration tests — real database round-trips through the repository layer.

These hit the database defined by the POSTGRES_* env vars (defaults:
localhost:5432, postgres/postgres, projectdb). Throwaway parent projects and
resources are created for the allocations to reference; deleting them cascades to
the allocations (ON DELETE CASCADE), so cleanup is guaranteed. The whole module
auto-skips when the database or `allocations` schema is unavailable, so the
unit/api/security suites still run anywhere.

    POSTGRES_NAME=projectdb pytest -m integration
"""

import json

import pytest

import auth
import function
import postgres_service
import testkit
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

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not testkit.database_ready("allocations"),
        reason="local PostgreSQL with the allocations schema is not available",
    ),
]


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

def test_reference_helpers_report_existence(env):
    assert resource_exists(env["r1"]) is True
    assert project_exists(env["p1"]) is True
    assert resource_exists(2_000_000_000) is False
    assert project_exists(2_000_000_000) is False


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def test_create_persists_row_and_applies_default_pct(env):
    a = create_allocation({"resource_id": env["r1"], "project_id": env["p1"]})
    assert a["id"] is not None
    assert a["resource_id"] == env["r1"]
    assert a["allocation_pct"] == 0  # COALESCE default


def test_get_returns_created_row_and_none_when_missing(env):
    a = create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 30})
    assert get_allocation(a["id"])["allocation_pct"] == 30
    assert get_allocation(2_000_000_000) is None


def test_list_honours_resource_and_project_filters(env):
    a1 = create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 10})
    a2 = create_allocation({"resource_id": env["r1"], "project_id": env["p2"], "allocation_pct": 20})
    a3 = create_allocation({"resource_id": env["r2"], "project_id": env["p1"], "allocation_pct": 30})

    by_resource = list_allocations(resource_id=env["r1"], limit=200)
    ids = {a["id"] for a in by_resource["items"]}
    assert a1["id"] in ids and a2["id"] in ids and a3["id"] not in ids
    assert by_resource["total"] == 2 and by_resource["limit"] == 200

    by_project = list_allocations(project_id=env["p1"], limit=200)
    ids = {a["id"] for a in by_project["items"]}
    assert a1["id"] in ids and a3["id"] in ids and a2["id"] not in ids

    both = list_allocations(resource_id=env["r1"], project_id=env["p2"])
    assert [a["id"] for a in both["items"]] == [a2["id"]]
    assert both["total"] == 1


def test_partial_update_preserves_other_fields(env):
    a = create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 40})
    updated = update_allocation(a["id"], {"allocation_pct": 80})
    assert updated["allocation_pct"] == 80
    assert updated["resource_id"] == env["r1"]
    assert updated["project_id"] == env["p1"]


def test_update_missing_id_returns_none():
    assert update_allocation(2_000_000_000, {"allocation_pct": 10}) is None


def test_delete_removes_row_and_is_idempotent(env):
    a = create_allocation({"resource_id": env["r2"], "project_id": env["p2"], "allocation_pct": 5})
    assert delete_allocation(a["id"])["id"] == a["id"]
    assert get_allocation(a["id"]) is None
    assert delete_allocation(a["id"]) is None


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

def test_duplicate_pair_raises_duplicate_allocation_error(env):
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


def test_pagination_slices_pages_and_counts_total(env):
    create_allocation({"resource_id": env["r1"], "project_id": env["p1"], "allocation_pct": 10})
    create_allocation({"resource_id": env["r1"], "project_id": env["p2"], "allocation_pct": 20})
    page1 = list_allocations(resource_id=env["r1"], limit=1, offset=0)
    page2 = list_allocations(resource_id=env["r1"], limit=1, offset=1)
    assert page1["total"] == 2 and page2["total"] == 2
    assert len(page1["items"]) == 1 and len(page2["items"]) == 1
    assert page1["items"][0]["id"] != page2["items"][0]["id"]  # distinct pages


def test_exactly_100_percent_is_not_over_allocated(env):
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


# ---------------------------------------------------------------------------
# ?search= — matches the RELATED resource name or project name (subquery join)
# ---------------------------------------------------------------------------

def test_search_matches_related_resource_name():
    p = _mk_project("Srch Alloc Proj Ordinary")
    r = _mk_resource("Quibble Searchable Person", "quibble-alloc@example-test.invalid")
    a = create_allocation({"resource_id": r, "project_id": p, "allocation_pct": 25})
    try:
        ids = {x["id"] for x in list_allocations(search="quibble", limit=200)["items"]}
        assert a["id"] in ids          # found via the resource's name
        # Case-insensitive.
        assert a["id"] in {x["id"] for x in list_allocations(search="QUIBBLE", limit=200)["items"]}
    finally:
        postgres_service.execute("DELETE FROM projects WHERE id = %s", (p,))
        postgres_service.execute("DELETE FROM resources WHERE id = %s", (r,))


def test_search_matches_related_project_name():
    p = _mk_project("Wobblethon Analytics")
    r = _mk_resource("Srch Alloc Person Ordinary", "srch-alloc-person@example-test.invalid")
    a = create_allocation({"resource_id": r, "project_id": p, "allocation_pct": 40})
    try:
        ids = {x["id"] for x in list_allocations(search="wobblethon", limit=200)["items"]}
        assert a["id"] in ids          # found via the project's name
    finally:
        postgres_service.execute("DELETE FROM projects WHERE id = %s", (p,))
        postgres_service.execute("DELETE FROM resources WHERE id = %s", (r,))


def test_search_combines_with_resource_filter():
    p = _mk_project("Combine Alloc Proj")
    r1 = _mk_resource("Combine Zorptastic One", "combine-alloc-1@example-test.invalid")
    r2 = _mk_resource("Combine Zorptastic Two", "combine-alloc-2@example-test.invalid")
    a1 = create_allocation({"resource_id": r1, "project_id": p, "allocation_pct": 10})
    a2 = create_allocation({"resource_id": r2, "project_id": p, "allocation_pct": 20})
    try:
        # Both match the search "zorptastic", but the resource_id filter keeps only a1.
        res = list_allocations(search="zorptastic", resource_id=r1, limit=200)
        ids = {x["id"] for x in res["items"]}
        assert a1["id"] in ids
        assert a2["id"] not in ids
        # No duplicate rows from the subquery join.
        assert res["total"] == len(res["items"])
    finally:
        postgres_service.execute("DELETE FROM projects WHERE id = %s", (p,))
        for rid in (r1, r2):
            postgres_service.execute("DELETE FROM resources WHERE id = %s", (rid,))


def test_search_with_no_match_is_empty():
    assert list_allocations(search="__no_such_alloc_zzz__", limit=200)["total"] == 0


# ---------------------------------------------------------------------------
# Activity log written through the real handler (create / update / delete)
#
# Allocations have no name of their own, so the entity_name is a readable
# 'Resource on Project' label.
# ---------------------------------------------------------------------------

@pytest.fixture
def activity_ctx():
    """A real user, resource, and project (so FKs are satisfied) plus a token."""
    uid = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) "
        "VALUES (%s,%s,%s,(SELECT id FROM roles WHERE name='Admin')) RETURNING id",
        ("alloc-act-actor", "alloc-act-actor@example-test.invalid", "x"), fetch="one")["id"]
    rid = postgres_service.execute(
        "INSERT INTO resources (name, email) VALUES (%s,%s) RETURNING id",
        ("Alloc Act Resource", "alloc-act-res@example-test.invalid"), fetch="one")["id"]
    pid = postgres_service.execute(
        "INSERT INTO projects (name) VALUES (%s) RETURNING id", ("Alloc Act Project",), fetch="one")["id"]
    token = auth.create_token({"sub": str(uid), "username": "alloc-act-actor", "role": "Admin"})
    yield {"uid": uid, "rid": rid, "pid": pid, "token": token}
    postgres_service.execute("DELETE FROM projects WHERE id = %s", (pid,))   # cascades allocations
    postgres_service.execute("DELETE FROM resources WHERE id = %s", (rid,))
    postgres_service.execute("DELETE FROM users WHERE id = %s", (uid,))


def _latest_activity(entity_id, action):
    return postgres_service.execute(
        "SELECT * FROM activity_log WHERE entity_type='allocation' AND entity_id=%s AND action=%s "
        "ORDER BY id DESC LIMIT 1", (entity_id, action), fetch="one")


def test_create_update_delete_each_write_an_activity_entry(activity_ctx):
    token = activity_ctx["token"]
    hdr = {"Authorization": f"Bearer {token}"}

    created = function.handler(testkit.make_event(
        "POST", "/allocations",
        body={"resource_id": activity_ctx["rid"], "project_id": activity_ctx["pid"], "allocation_pct": 40},
        headers=hdr))
    aid = json.loads(created["body"])["id"]

    row = _latest_activity(aid, "created")
    assert row and row["user_id"] == activity_ctx["uid"]
    # name-less entity -> readable 'Resource on Project' label
    assert row["entity_name"] == "Alloc Act Resource on Alloc Act Project"

    function.handler(testkit.make_event("PUT", f"/allocations/{aid}", body={"allocation_pct": 75}, headers=hdr))
    upd = _latest_activity(aid, "updated")
    assert upd and {"field": "allocation_pct", "old": 40, "new": 75} in upd["changes"]

    function.handler(testkit.make_event("DELETE", f"/allocations/{aid}", headers=hdr))
    assert _latest_activity(aid, "deleted") is not None
