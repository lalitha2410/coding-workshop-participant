"""
Integration tests for the projects service against a real local PostgreSQL.

These hit the database defined by the POSTGRES_* env vars (defaults:
localhost:5432, postgres/postgres, projectdb) and run through the repository
layer. They are skipped automatically when the database or `projects` table is
unavailable, so the unit suite still runs anywhere.

Run against the local dev database with the schema loaded:
    POSTGRES_NAME=projectdb pytest backend/projects/tests/test_integration.py
"""

import pytest

import postgres_service
from projects_repository import (
    list_projects,
    get_project,
    create_project,
    update_project,
    delete_project,
)


def _database_ready():
    """True if we can connect and the projects table exists."""
    try:
        postgres_service.execute("SELECT 1 FROM projects LIMIT 1", fetch="one")
        return True
    except Exception:
        # Reset the pooled connection so a failed probe doesn't poison later calls.
        postgres_service.PG_CONN = None
        return False


# Skip the whole module if the database isn't reachable / seeded.
pytestmark = pytest.mark.skipif(
    not _database_ready(),
    reason="local PostgreSQL with the projects schema is not available",
)


@pytest.fixture
def created_project():
    """Create a throwaway project and guarantee cleanup afterwards."""
    project = create_project({
        "name": "Integration Test Project",
        "description": "created by test_integration",
        "status": "planning",
        "department": "QA",
        "budget_planned": 500,
    })
    yield project
    # Best-effort cleanup even if the test deleted it already.
    delete_project(project["id"])


def test_create_persists_and_defaults(created_project):
    assert created_project["id"] is not None
    assert created_project["name"] == "Integration Test Project"
    # COALESCE defaults from create_project.
    assert created_project["status"] == "planning"
    assert float(created_project["budget_consumed"]) == 0.0


def test_get_returns_created_row(created_project):
    fetched = get_project(created_project["id"])
    assert fetched is not None
    assert fetched["id"] == created_project["id"]


def test_get_missing_returns_none():
    assert get_project(2_000_000_000) is None


def test_list_includes_created_and_filters(created_project):
    all_rows = list_projects()
    assert any(p["id"] == created_project["id"] for p in all_rows)

    qa_rows = list_projects(department="QA")
    assert all(p["department"] == "QA" for p in qa_rows)
    assert any(p["id"] == created_project["id"] for p in qa_rows)

    # A department that shouldn't match our row.
    none_rows = list_projects(department="__no_such_department__")
    assert all(p["id"] != created_project["id"] for p in none_rows)


def test_partial_update_preserves_other_fields(created_project):
    updated = update_project(created_project["id"], {"status": "active"})
    assert updated["status"] == "active"
    # COALESCE partial update leaves untouched fields intact.
    assert updated["name"] == created_project["name"]
    assert updated["department"] == "QA"
    # updated_at bumped to NOW() on update.
    assert updated["updated_at"] >= created_project["updated_at"]


def test_update_missing_returns_none():
    assert update_project(2_000_000_000, {"status": "active"}) is None


def test_delete_removes_row():
    project = create_project({"name": "To Be Deleted"})
    deleted = delete_project(project["id"])
    assert deleted is not None and deleted["id"] == project["id"]
    assert get_project(project["id"]) is None
    # Deleting again is a no-op that returns None.
    assert delete_project(project["id"]) is None
