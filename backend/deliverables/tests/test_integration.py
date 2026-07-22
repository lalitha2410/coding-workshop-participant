"""
Integration tests for the deliverables service against a real local PostgreSQL.

These hit the database defined by the POSTGRES_* env vars (defaults:
localhost:5432, postgres/postgres, projectdb) and run through the repository
layer. A throwaway parent project is created for the deliverables to reference;
deleting it cascades to any child deliverables (ON DELETE CASCADE), so cleanup
is guaranteed. The whole module auto-skips when the DB or schema is unavailable.

Run against the local dev database with the schema loaded:
    IS_LOCAL=true pytest backend/deliverables/tests/test_integration.py
"""

import pytest

import postgres_service
from deliverables_repository import (
    list_deliverables,
    get_deliverable,
    create_deliverable,
    update_deliverable,
    delete_deliverable,
    project_exists,
)


def _database_ready():
    """True if we can connect and the deliverables table exists."""
    try:
        postgres_service.execute("SELECT 1 FROM deliverables LIMIT 1", fetch="one")
        return True
    except Exception:
        postgres_service.PG_CONN = None
        return False


pytestmark = pytest.mark.skipif(
    not _database_ready(),
    reason="local PostgreSQL with the deliverables schema is not available",
)


@pytest.fixture
def parent_project():
    """Create a throwaway parent project; deleting it cascades to deliverables."""
    project = postgres_service.execute(
        "INSERT INTO projects (name, status) VALUES (%s, 'planning') RETURNING id",
        ("Deliverables IT Parent",),
        fetch="one",
    )
    yield project["id"]
    postgres_service.execute("DELETE FROM projects WHERE id = %s", (project["id"],))


@pytest.fixture
def created_deliverable(parent_project):
    """Create a deliverable under the throwaway parent project."""
    return create_deliverable({
        "project_id": parent_project,
        "name": "IT Deliverable",
        "description": "created by test_integration",
        "status": "not_started",
    })


def test_project_exists_helper(parent_project):
    assert project_exists(parent_project) is True
    assert project_exists(2_000_000_000) is False


def test_create_persists_and_defaults(created_deliverable):
    assert created_deliverable["id"] is not None
    assert created_deliverable["name"] == "IT Deliverable"
    # COALESCE defaults from create_deliverable.
    assert created_deliverable["status"] == "not_started"
    assert created_deliverable["completion_pct"] == 0


def test_get_returns_created_row(created_deliverable):
    fetched = get_deliverable(created_deliverable["id"])
    assert fetched is not None
    assert fetched["id"] == created_deliverable["id"]


def test_get_missing_returns_none():
    assert get_deliverable(2_000_000_000) is None


def test_list_filters_by_project_and_status(parent_project, created_deliverable):
    by_project = list_deliverables(project_id=parent_project, limit=200)
    assert all(d["project_id"] == parent_project for d in by_project["items"])
    assert any(d["id"] == created_deliverable["id"] for d in by_project["items"])
    assert by_project["total"] >= 1 and by_project["limit"] == 200

    by_status = list_deliverables(project_id=parent_project, status="not_started")
    assert any(d["id"] == created_deliverable["id"] for d in by_status["items"])

    none_match = list_deliverables(project_id=parent_project, status="completed")
    assert none_match["total"] == 0 and none_match["items"] == []


def test_pagination_slices_and_counts(parent_project):
    made = [create_deliverable({"project_id": parent_project, "name": f"Pag IT {i}"}) for i in range(3)]
    page1 = list_deliverables(project_id=parent_project, limit=2, offset=0)
    page2 = list_deliverables(project_id=parent_project, limit=2, offset=2)
    assert page1["total"] == 3 and page2["total"] == 3
    assert len(page1["items"]) == 2 and len(page2["items"]) == 1
    ids1 = {d["id"] for d in page1["items"]}
    ids2 = {d["id"] for d in page2["items"]}
    assert ids1.isdisjoint(ids2)
    # No explicit cleanup needed: deleting the parent project cascades.


def test_sql_injection_payload_stored_literally(parent_project):
    payload = "'; DROP TABLE deliverables;--"
    created = create_deliverable({"project_id": parent_project, "name": payload})
    assert get_deliverable(created["id"])["name"] == payload  # literal data, not executed
    assert list_deliverables(project_id=parent_project, limit=10)["total"] >= 1  # table intact


def test_long_text_description_is_accepted(parent_project):
    created = create_deliverable({"project_id": parent_project, "name": "Long Desc", "description": "y" * 10000})
    assert len(get_deliverable(created["id"])["description"]) == 10000


def test_partial_update_preserves_other_fields(created_deliverable):
    updated = update_deliverable(created_deliverable["id"], {"completion_pct": 50})
    assert updated["completion_pct"] == 50
    # COALESCE partial update leaves untouched fields intact.
    assert updated["name"] == created_deliverable["name"]
    assert updated["status"] == "not_started"
    # updated_at bumped to NOW() on update.
    assert updated["updated_at"] >= created_deliverable["updated_at"]


def test_update_missing_returns_none():
    assert update_deliverable(2_000_000_000, {"status": "completed"}) is None


def test_delete_removes_row(parent_project):
    deliverable = create_deliverable({"project_id": parent_project, "name": "To Be Deleted"})
    deleted = delete_deliverable(deliverable["id"])
    assert deleted is not None and deleted["id"] == deliverable["id"]
    assert get_deliverable(deliverable["id"]) is None
    # Deleting again is a no-op that returns None.
    assert delete_deliverable(deliverable["id"]) is None


def test_create_with_missing_project_raises(parent_project):
    # The repository does not pre-check the FK; the DB rejects the orphan insert.
    # (The handler layer guards this with project_exists before calling create.)
    import psycopg
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        create_deliverable({"project_id": 2_000_000_000, "name": "Orphan"})
    # Reset the pooled connection soured by the failed transaction.
    postgres_service.PG_CONN = None
