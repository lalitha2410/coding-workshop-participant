"""
Integration tests — real database round-trips through the repository layer.

These hit the database defined by the POSTGRES_* env vars (defaults:
localhost:5432, postgres/postgres, projectdb). They skip automatically when the
database or `projects` table is unavailable, so the unit/api/security suites
still run anywhere.

    POSTGRES_NAME=projectdb pytest -m integration
"""

import json

import pytest

import auth
import function
import postgres_service
import testkit
from projects_repository import (
    list_projects, get_project, create_project, update_project, delete_project,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not testkit.database_ready("projects"),
        reason="local PostgreSQL with the projects schema is not available",
    ),
]


@pytest.fixture
def created_project():
    """Create a throwaway project and guarantee cleanup afterwards."""
    project = create_project({
        "name": "Integration Test Project", "description": "created by test_integration",
        "status": "planning", "department": "QA", "budget_planned": 500,
    })
    yield project
    delete_project(project["id"])  # best-effort even if the test deleted it


# ---------------------------------------------------------------------------
# CRUD round-trips
# ---------------------------------------------------------------------------

def test_create_persists_row_and_applies_defaults(created_project):
    assert created_project["id"] is not None
    assert created_project["name"] == "Integration Test Project"
    assert created_project["status"] == "planning"           # COALESCE default
    assert float(created_project["budget_consumed"]) == 0.0


def test_get_returns_the_created_row(created_project):
    fetched = get_project(created_project["id"])
    assert fetched is not None and fetched["id"] == created_project["id"]


def test_get_missing_id_returns_none():
    assert get_project(2_000_000_000) is None


def test_list_includes_created_row_and_honours_filters(created_project):
    qa = list_projects(department="QA", limit=200)
    assert qa["items"] and all(p["department"] == "QA" for p in qa["items"])
    assert any(p["id"] == created_project["id"] for p in qa["items"])
    assert qa["total"] >= 1 and qa["limit"] == 200 and qa["offset"] == 0

    none_rows = list_projects(department="__no_such_department__")
    assert none_rows["total"] == 0 and none_rows["items"] == []


def test_pagination_slices_pages_and_counts_total():
    made = [create_project({"name": f"Pag IT {i}", "department": "PAG-IT"}) for i in range(3)]
    try:
        page1 = list_projects(department="PAG-IT", limit=2, offset=0)
        page2 = list_projects(department="PAG-IT", limit=2, offset=2)
        assert page1["total"] == 3 and page2["total"] == 3
        assert len(page1["items"]) == 2 and len(page2["items"]) == 1
        assert {p["id"] for p in page1["items"]}.isdisjoint({p["id"] for p in page2["items"]})
    finally:
        for p in made:
            delete_project(p["id"])


def test_long_text_description_is_accepted():
    # description is TEXT (unbounded) -> a very long value is accepted, not a 500.
    created = create_project({"name": "Long Desc IT", "description": "x" * 10000})
    try:
        assert len(get_project(created["id"])["description"]) == 10000
    finally:
        delete_project(created["id"])


def test_partial_update_preserves_other_fields(created_project):
    updated = update_project(created_project["id"], {"status": "active"})
    assert updated["status"] == "active"
    assert updated["name"] == created_project["name"]        # COALESCE untouched
    assert updated["department"] == "QA"
    assert updated["updated_at"] >= created_project["updated_at"]


def test_update_missing_id_returns_none():
    assert update_project(2_000_000_000, {"status": "active"}) is None


def test_delete_removes_row_and_is_idempotent():
    project = create_project({"name": "To Be Deleted"})
    deleted = delete_project(project["id"])
    assert deleted is not None and deleted["id"] == project["id"]
    assert get_project(project["id"]) is None
    assert delete_project(project["id"]) is None  # deleting again is a no-op


# ---------------------------------------------------------------------------
# ?search= against the database (alongside status/department filters)
# ---------------------------------------------------------------------------

def test_search_matches_name_and_description():
    by_name = create_project({"name": "Zephyr Search IT", "department": "SRCH-IT", "description": "alpha"})
    by_desc = create_project({"name": "Unrelated IT", "department": "SRCH-IT", "description": "a zephyr in prose"})
    try:
        hits = list_projects(search="zephyr", limit=200)
        ids = {p["id"] for p in hits["items"]}
        assert by_name["id"] in ids and by_desc["id"] in ids     # name + description
        assert by_name["id"] in {p["id"] for p in list_projects(search="ZEPHYR", limit=200)["items"]}
        assert hits["total"] == len(hits["items"])
    finally:
        delete_project(by_name["id"])
        delete_project(by_desc["id"])


def test_search_combines_with_status_filter():
    hit = create_project({"name": "Combine Zorp", "department": "CMB-IT", "status": "active"})
    miss = create_project({"name": "Combine Zorp", "department": "CMB-IT", "status": "planning"})
    try:
        ids = {p["id"] for p in list_projects(search="zorp", status="active", limit=200)["items"]}
        assert hit["id"] in ids and miss["id"] not in ids
    finally:
        delete_project(hit["id"])
        delete_project(miss["id"])


def test_search_with_no_match_is_empty():
    assert list_projects(search="__no_such_project_zzz__", limit=200)["total"] == 0


def test_search_treats_wildcards_literally():
    # '%' is a bound parameter, not a LIKE match-all — finds text containing it.
    p = create_project({"name": "Loadfactor 99pct", "department": "WILD-IT"})
    try:
        assert any(x["id"] == p["id"] for x in list_projects(search="99pct", limit=200)["items"])
    finally:
        delete_project(p["id"])


# ---------------------------------------------------------------------------
# Activity log written through the real handler (create / update / delete)
# ---------------------------------------------------------------------------

@pytest.fixture
def actor_user():
    """A real user row (so the activity FK is satisfied) plus a token for them."""
    row = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) "
        "VALUES (%s, %s, %s, (SELECT id FROM roles WHERE name='Admin')) RETURNING id",
        ("activity-it-actor", "activity-it-actor@example-test.invalid", "x"), fetch="one",
    )
    uid = row["id"]
    token = auth.create_token({"sub": str(uid), "username": "activity-it-actor", "role": "Admin"})
    yield {"id": uid, "token": token}
    postgres_service.execute("DELETE FROM users WHERE id = %s", (uid,))


def _latest_activity(entity_id, action):
    return postgres_service.execute(
        "SELECT * FROM activity_log WHERE entity_type='project' AND entity_id=%s AND action=%s "
        "ORDER BY id DESC LIMIT 1", (entity_id, action), fetch="one",
    )


def test_create_update_delete_each_write_an_activity_entry(actor_user):
    hdr = {"Authorization": f"Bearer {actor_user['token']}"}

    created = function.handler(testkit.make_event(
        "POST", "/projects", body={"name": "Activity IT Project", "status": "planning"}, headers=hdr))
    pid = json.loads(created["body"])["id"]
    try:
        row = _latest_activity(pid, "created")
        assert row is not None
        assert row["user_id"] == actor_user["id"] and row["username"] == "activity-it-actor"
        assert row["entity_name"] == "Activity IT Project"
        assert row["changes"] is None  # creates carry no field-level diff

        function.handler(testkit.make_event("PUT", f"/projects/{pid}", body={"status": "active"}, headers=hdr))
        upd = _latest_activity(pid, "updated")
        assert upd is not None
        assert upd["changes"] == [{"field": "status", "old": "planning", "new": "active"}]

        function.handler(testkit.make_event("DELETE", f"/projects/{pid}", headers=hdr))
        deleted = _latest_activity(pid, "deleted")
        assert deleted is not None and deleted["entity_name"] == "Activity IT Project"
    finally:
        postgres_service.execute("DELETE FROM projects WHERE id = %s", (pid,))
        postgres_service.execute("DELETE FROM activity_log WHERE entity_id = %s AND entity_type='project'", (pid,))
