"""
Security tests — authentication, the RBAC gate, and injection resistance.

The permission tests run against a mocked repository (no DB) with explicit bearer
tokens, so they assert the gate independently of business logic. One end-to-end
injection test is DB-backed and skips when no database is available.
"""

import json
from datetime import datetime

import pytest

import function
import testkit
from testkit import bearer
from resources_repository import create_resource, get_resource, list_resources, delete_resource

pytestmark = pytest.mark.security

requires_db = pytest.mark.skipif(
    not testkit.database_ready("resources"),
    reason="local PostgreSQL with the resources schema is not available",
)

SAMPLE_RESOURCE = {
    "id": 1,
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "title": "Principal Engineer",
    "created_at": datetime(2026, 1, 1, 12, 0, 0),
}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_request_without_a_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/resources", "headers": {}})
    assert resp["statusCode"] == 401


def test_request_with_invalid_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/resources",
                             "headers": {"Authorization": "Bearer not.a.jwt"}})
    assert resp["statusCode"] == 401


def test_deleted_user_token_returns_401(repo, monkeypatch):
    # Validly-signed token, but the subject no longer exists -> fail safe (401).
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: False)
    resp = function.handler({"httpMethod": "GET", "path": "/resources", "headers": bearer("Admin")})
    assert resp["statusCode"] == 401


def test_unknown_role_token_returns_403(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/resources", "headers": bearer("Wizard")})
    assert resp["statusCode"] == 403


# ---------------------------------------------------------------------------
# RBAC — read/create/delete by role
# ---------------------------------------------------------------------------

def test_viewer_can_read(repo):
    repo.set("list_resources", [])
    resp = function.handler({"httpMethod": "GET", "path": "/resources", "headers": bearer("Viewer")})
    assert resp["statusCode"] == 200


def test_viewer_cannot_create_returns_403(repo):
    repo.set("create_resource", SAMPLE_RESOURCE)  # must not be reached
    resp = function.handler({"httpMethod": "POST", "path": "/resources",
                             "headers": bearer("Viewer"),
                             "body": json.dumps({"name": "X", "email": "x@example.com"})})
    assert resp["statusCode"] == 403
    assert "create_resource" not in repo.calls


def test_contributor_can_create_returns_201(repo):
    repo.set("create_resource", SAMPLE_RESOURCE)
    resp = function.handler({"httpMethod": "POST", "path": "/resources",
                             "headers": bearer("Contributor"),
                             "body": json.dumps({"name": "X", "email": "x@example.com"})})
    assert resp["statusCode"] == 201


def test_contributor_cannot_delete_returns_403(repo):
    repo.set("delete_resource", {"id": 1})  # must not be reached
    resp = function.handler({"httpMethod": "DELETE", "path": "/resources/1", "headers": bearer("Contributor")})
    assert resp["statusCode"] == 403
    assert "delete_resource" not in repo.calls


def test_manager_can_delete_returns_204(repo):
    repo.set("delete_resource", {"id": 1, "name": "Marcus Reed"})
    resp = function.handler({"httpMethod": "DELETE", "path": "/resources/1", "headers": bearer("Manager")})
    assert resp["statusCode"] == 204


# ---------------------------------------------------------------------------
# Injection resistance
# ---------------------------------------------------------------------------

def test_sql_injection_name_reaches_repository_verbatim(repo):
    # The handler passes the raw string to the parameterized repository; nothing
    # is executed. Assert it arrives at create_resource untouched.
    repo.set("create_resource", SAMPLE_RESOURCE)
    payload = "'; DROP TABLE resources;--"
    resp = function.handler({"httpMethod": "POST", "path": "/resources",
                             "body": json.dumps({"name": payload, "email": "a@b.com"})})
    assert resp["statusCode"] == 201
    assert repo.calls["create_resource"]["args"][0]["name"] == payload


@requires_db
def test_sql_injection_payload_is_stored_literally():
    payload = "'; DROP TABLE resources;--"
    created = create_resource({"name": payload, "email": "sqli-it@example-test.invalid"})
    try:
        assert get_resource(created["id"])["name"] == payload  # literal data, not executed
        assert list_resources(search="DROP TABLE", limit=10)["total"] >= 1  # table intact
    finally:
        delete_resource(created["id"])
