"""
Security tests — authentication, the RBAC gate, and injection resistance.

The permission tests run against a mocked repository (no DB) with explicit bearer
tokens, so they assert the gate independently of business logic. One end-to-end
injection test is DB-backed and skips when no database is available.
"""

import json
from datetime import date

import pytest

import function
import postgres_service
import testkit
from testkit import bearer
from deliverables_repository import (
    create_deliverable, get_deliverable, list_deliverables,
)

pytestmark = pytest.mark.security

requires_db = pytest.mark.skipif(
    not testkit.database_ready("deliverables"),
    reason="local PostgreSQL with the deliverables schema is not available",
)

SAMPLE_DELIVERABLE = {
    "id": 1,
    "project_id": 10,
    "name": "Design doc",
    "status": "in_progress",
    "completion_pct": 40,
    "due_date": date(2026, 6, 30),
}


@pytest.fixture(autouse=True)
def _project_exists_true(monkeypatch):
    """Referenced project exists by default so create/update reach the DB layer;
    tests asserting the missing-project path override this themselves."""
    monkeypatch.setattr(function, "project_exists", lambda pid: True)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_request_without_a_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables", "headers": {}})
    assert resp["statusCode"] == 401


def test_request_with_invalid_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables",
                             "headers": {"Authorization": "Bearer not.a.jwt"}})
    assert resp["statusCode"] == 401


def test_deleted_user_token_returns_401(repo, monkeypatch):
    # Validly-signed token, but the subject no longer exists -> fail safe (401).
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: False)
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables", "headers": bearer("Admin")})
    assert resp["statusCode"] == 401


def test_unknown_role_token_returns_403(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables", "headers": bearer("Wizard")})
    assert resp["statusCode"] == 403


# ---------------------------------------------------------------------------
# RBAC — read/create/delete by role
# ---------------------------------------------------------------------------

def test_viewer_can_read(repo):
    repo.set("list_deliverables", [])
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables", "headers": bearer("Viewer")})
    assert resp["statusCode"] == 200


def test_viewer_cannot_create_returns_403(repo):
    repo.set("create_deliverable", SAMPLE_DELIVERABLE)  # must not be reached
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables",
                             "headers": bearer("Viewer"),
                             "body": json.dumps({"project_id": 10, "name": "X"})})
    assert resp["statusCode"] == 403
    assert "create_deliverable" not in repo.calls


def test_contributor_can_create_returns_201(repo):
    repo.set("create_deliverable", SAMPLE_DELIVERABLE)
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables",
                             "headers": bearer("Contributor"),
                             "body": json.dumps({"project_id": 10, "name": "X"})})
    assert resp["statusCode"] == 201


def test_contributor_cannot_delete_returns_403(repo):
    repo.set("delete_deliverable", {"id": 1})  # must not be reached
    resp = function.handler({"httpMethod": "DELETE", "path": "/deliverables/1", "headers": bearer("Contributor")})
    assert resp["statusCode"] == 403
    assert "delete_deliverable" not in repo.calls


def test_manager_can_delete_returns_204(repo):
    repo.set("delete_deliverable", {"id": 1, "name": "Beta"})
    resp = function.handler({"httpMethod": "DELETE", "path": "/deliverables/1", "headers": bearer("Manager")})
    assert resp["statusCode"] == 204


# ---------------------------------------------------------------------------
# RBAC — dependency routes
# ---------------------------------------------------------------------------

def test_add_dependency_viewer_returns_403(repo, monkeypatch):
    monkeypatch.setattr(function, "deliverable_exists", lambda i: True)
    monkeypatch.setattr(function, "add_dependency", lambda d, o: {"deliverable_id": d, "depends_on_id": o})
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables/5/dependencies",
                             "headers": bearer("Viewer"), "body": json.dumps({"depends_on_id": 2})})
    assert resp["statusCode"] == 403


def test_add_dependency_contributor_returns_201(repo, monkeypatch):
    monkeypatch.setattr(function, "deliverable_exists", lambda i: True)
    monkeypatch.setattr(function, "path_exists", lambda a, b: False)
    monkeypatch.setattr(function, "add_dependency", lambda d, o: {"deliverable_id": d, "depends_on_id": o})
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables/5/dependencies",
                             "headers": bearer("Contributor"), "body": json.dumps({"depends_on_id": 2})})
    assert resp["statusCode"] == 201


def test_remove_dependency_contributor_returns_204(repo, monkeypatch):
    # Contributor+ can remove a dependency (it is NOT Manager-only like a deliverable delete).
    monkeypatch.setattr(function, "remove_dependency", lambda d, o: {"deliverable_id": d, "depends_on_id": o})
    resp = function.handler({"httpMethod": "DELETE", "path": "/deliverables/5/dependencies/2", "headers": bearer("Contributor")})
    assert resp["statusCode"] == 204


def test_remove_dependency_viewer_returns_403(repo, monkeypatch):
    called = {}
    monkeypatch.setattr(function, "remove_dependency", lambda d, o: called.update(hit=True))
    resp = function.handler({"httpMethod": "DELETE", "path": "/deliverables/5/dependencies/2", "headers": bearer("Viewer")})
    assert resp["statusCode"] == 403
    assert "hit" not in called


# ---------------------------------------------------------------------------
# Injection resistance
# ---------------------------------------------------------------------------

def test_sql_injection_name_reaches_repository_verbatim(repo):
    # The handler passes the raw string to the parameterized repository; nothing
    # is executed. Assert it arrives at create_deliverable untouched.
    repo.set("create_deliverable", SAMPLE_DELIVERABLE)
    payload = "'; DROP TABLE deliverables;--"
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables",
                             "body": json.dumps({"project_id": 10, "name": payload})})
    assert resp["statusCode"] == 201
    assert repo.calls["create_deliverable"]["args"][0]["name"] == payload


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


@requires_db
def test_sql_injection_payload_is_stored_literally(parent_project):
    payload = "'; DROP TABLE deliverables;--"
    created = create_deliverable({"project_id": parent_project, "name": payload})
    assert get_deliverable(created["id"])["name"] == payload  # literal data, not executed
    assert list_deliverables(project_id=parent_project, limit=10)["total"] >= 1  # table intact
