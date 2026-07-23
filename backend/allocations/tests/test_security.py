"""
Security tests — authentication and the RBAC gate.

The permission tests run against a mocked repository (no DB) with explicit bearer
tokens, so they assert the gate independently of business logic. Analytics reads
are available to any authenticated role but still require a valid token.
"""

import json
from datetime import date

import pytest

import function
from testkit import bearer

pytestmark = pytest.mark.security


SAMPLE_ALLOCATION = {
    "id": 1,
    "resource_id": 10,
    "project_id": 20,
    "allocation_pct": 50,
    "start_date": date(2026, 1, 1),
    "end_date": date(2026, 6, 30),
}


@pytest.fixture(autouse=True)
def _references_exist(monkeypatch):
    """By default both referenced rows exist, so an authorized create reaches the
    DB layer (letting the RBAC gate, not a missing FK, decide the outcome)."""
    monkeypatch.setattr(function, "resource_exists", lambda rid: True)
    monkeypatch.setattr(function, "project_exists", lambda pid: True)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_request_without_a_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/allocations", "headers": {}})
    assert resp["statusCode"] == 401


def test_request_with_invalid_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/allocations",
                             "headers": {"Authorization": "Bearer not.a.jwt"}})
    assert resp["statusCode"] == 401


def test_deleted_user_token_returns_401(repo, monkeypatch):
    # Validly-signed token, but the subject no longer exists -> fail safe (401).
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: False)
    resp = function.handler({"httpMethod": "GET", "path": "/allocations", "headers": bearer("Admin")})
    assert resp["statusCode"] == 401


def test_unknown_role_token_returns_403(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/allocations", "headers": bearer("Wizard")})
    assert resp["statusCode"] == 403


def test_over_allocated_requires_token(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/allocations/over-allocated", "headers": {}})
    assert resp["statusCode"] == 401


# ---------------------------------------------------------------------------
# RBAC — read/create/delete by role
# ---------------------------------------------------------------------------

def test_viewer_can_read_list(repo):
    repo.set("list_allocations", [])
    resp = function.handler({"httpMethod": "GET", "path": "/allocations", "headers": bearer("Viewer")})
    assert resp["statusCode"] == 200


def test_viewer_can_read_over_allocated(repo):
    # Analytics endpoints are reads -> available to any authenticated role.
    repo.set("resource_allocation_totals", [])
    resp = function.handler({"httpMethod": "GET", "path": "/allocations/over-allocated",
                             "headers": bearer("Viewer")})
    assert resp["statusCode"] == 200


def test_viewer_cannot_create_returns_403(repo):
    repo.set("create_allocation", SAMPLE_ALLOCATION)  # must not be reached
    resp = function.handler({"httpMethod": "POST", "path": "/allocations",
                             "headers": bearer("Viewer"),
                             "body": json.dumps({"resource_id": 10, "project_id": 20})})
    assert resp["statusCode"] == 403
    assert "create_allocation" not in repo.calls


def test_contributor_can_create_returns_201(repo):
    repo.set("create_allocation", SAMPLE_ALLOCATION)
    resp = function.handler({"httpMethod": "POST", "path": "/allocations",
                             "headers": bearer("Contributor"),
                             "body": json.dumps({"resource_id": 10, "project_id": 20})})
    assert resp["statusCode"] == 201


def test_contributor_cannot_delete_returns_403(repo):
    repo.set("delete_allocation", {"id": 1})  # must not be reached
    resp = function.handler({"httpMethod": "DELETE", "path": "/allocations/1", "headers": bearer("Contributor")})
    assert resp["statusCode"] == 403
    assert "delete_allocation" not in repo.calls


def test_manager_can_delete_returns_204(repo):
    repo.set("delete_allocation", {"id": 1, "resource_id": 10, "project_id": 20})
    resp = function.handler({"httpMethod": "DELETE", "path": "/allocations/1", "headers": bearer("Manager")})
    assert resp["statusCode"] == 204
