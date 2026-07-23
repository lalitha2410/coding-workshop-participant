"""
Security tests — authentication, the RBAC gate, and injection resistance.

The permission tests run against a mocked repository (no DB) with explicit bearer
tokens, so they assert the gate independently of business logic. One end-to-end
injection test is DB-backed and skips when no database is available.
"""

import json
from datetime import date
from decimal import Decimal

import pytest

import function
import postgres_service
import testkit
from testkit import bearer
from projects_repository import create_project, get_project, list_projects, delete_project

pytestmark = pytest.mark.security

requires_db = pytest.mark.skipif(
    not testkit.database_ready("projects"),
    reason="local PostgreSQL with the projects schema is not available",
)

SAMPLE_PROJECT = {"id": 1, "name": "Apollo", "status": "active",
                  "budget_planned": Decimal("0"), "budget_consumed": Decimal("0"),
                  "start_date": date(2026, 1, 1)}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_request_without_a_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/projects", "headers": {}})
    assert resp["statusCode"] == 401


def test_request_with_invalid_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/projects",
                             "headers": {"Authorization": "Bearer not.a.jwt"}})
    assert resp["statusCode"] == 401


def test_deleted_user_token_returns_401(repo, monkeypatch):
    # Validly-signed token, but the subject no longer exists -> fail safe (401).
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: False)
    resp = function.handler({"httpMethod": "GET", "path": "/projects", "headers": bearer("Admin")})
    assert resp["statusCode"] == 401


def test_unknown_role_token_returns_403(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/projects", "headers": bearer("Wizard")})
    assert resp["statusCode"] == 403


# ---------------------------------------------------------------------------
# RBAC — read/create/delete by role
# ---------------------------------------------------------------------------

def test_viewer_can_read(repo):
    repo.set("list_projects", [])
    resp = function.handler({"httpMethod": "GET", "path": "/projects", "headers": bearer("Viewer")})
    assert resp["statusCode"] == 200


def test_viewer_cannot_create_returns_403(repo):
    repo.set("create_project", SAMPLE_PROJECT)  # must not be reached
    resp = function.handler({"httpMethod": "POST", "path": "/projects",
                             "headers": bearer("Viewer"), "body": json.dumps({"name": "X"})})
    assert resp["statusCode"] == 403
    assert "create_project" not in repo.calls


def test_contributor_can_create_returns_201(repo):
    repo.set("create_project", SAMPLE_PROJECT)
    resp = function.handler({"httpMethod": "POST", "path": "/projects",
                             "headers": bearer("Contributor"), "body": json.dumps({"name": "X"})})
    assert resp["statusCode"] == 201


def test_contributor_cannot_delete_returns_403(repo):
    repo.set("delete_project", {"id": 1})  # must not be reached
    resp = function.handler({"httpMethod": "DELETE", "path": "/projects/1", "headers": bearer("Contributor")})
    assert resp["statusCode"] == 403
    assert "delete_project" not in repo.calls


def test_manager_can_delete_returns_204(repo):
    repo.set("delete_project", {"id": 1, "name": "Apollo"})
    resp = function.handler({"httpMethod": "DELETE", "path": "/projects/1", "headers": bearer("Manager")})
    assert resp["statusCode"] == 204


# ---------------------------------------------------------------------------
# Injection resistance
# ---------------------------------------------------------------------------

def test_sql_injection_name_reaches_repository_verbatim(repo):
    # The handler passes the raw string to the parameterized repository; nothing
    # is executed. Assert it arrives at create_project untouched.
    repo.set("create_project", SAMPLE_PROJECT)
    payload = "'; DROP TABLE projects;--"
    resp = function.handler({"httpMethod": "POST", "path": "/projects", "body": json.dumps({"name": payload})})
    assert resp["statusCode"] == 201
    assert repo.calls["create_project"]["args"][0]["name"] == payload


@requires_db
def test_sql_injection_payload_is_stored_literally():
    payload = "'; DROP TABLE projects;--"
    created = create_project({"name": payload, "department": "SQLI-IT"})
    try:
        # Stored verbatim as data, not executed...
        assert get_project(created["id"])["name"] == payload
        # ...and the table is very much still there.
        assert list_projects(department="SQLI-IT", limit=10)["total"] >= 1
    finally:
        delete_project(created["id"])
