"""
Unit tests for the function.handler router (resources service).

The repository layer is monkeypatched, so these tests exercise routing, status
codes, request parsing, duplicate-email handling, and response shaping without
touching a database.
"""

import json
from datetime import datetime

import pytest

import auth
import function
from resources_repository import DuplicateEmailError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _body(response):
    """Parse the JSON body of a handler response (empty string -> None)."""
    raw = response["body"]
    return json.loads(raw) if raw else None


SAMPLE_RESOURCE = {
    "id": 1,
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "title": "Principal Engineer",
    "created_at": datetime(2026, 1, 1, 12, 0, 0),
}


@pytest.fixture
def repo(monkeypatch):
    """Replace repository calls on the function module with stub recorders."""
    calls = {}

    def record(name, return_value):
        def _fn(*args, **kwargs):
            calls[name] = {"args": args, "kwargs": kwargs}
            if isinstance(return_value, Exception):
                raise return_value
            return return_value
        return _fn

    class Repo:
        def set(self, name, return_value):
            monkeypatch.setattr(function, name, record(name, return_value))

        @property
        def calls(self):
            return calls

    return Repo()


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------

def test_list_returns_200_and_passes_search(repo):
    repo.set("list_resources", {"items": [SAMPLE_RESOURCE], "total": 1, "limit": 50, "offset": 0})
    event = {
        "httpMethod": "GET",
        "path": "/resources",
        "queryStringParameters": {"search": "ada"},
    }
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    body = _body(resp)
    assert body["items"][0]["name"] == "Ada Lovelace"
    assert body["total"] == 1 and body["limit"] == 50 and body["offset"] == 0
    assert repo.calls["list_resources"]["kwargs"] == {"search": "ada", "limit": 50, "offset": 0}


def test_list_without_search_passes_none(repo):
    repo.set("list_resources", {"items": [], "total": 0, "limit": 50, "offset": 0})
    resp = function.handler({"httpMethod": "GET", "path": "/resources"})
    assert resp["statusCode"] == 200
    assert repo.calls["list_resources"]["kwargs"] == {"search": None, "limit": 50, "offset": 0}


def test_get_one_found_returns_200(repo):
    repo.set("get_resource", SAMPLE_RESOURCE)
    resp = function.handler({"httpMethod": "GET", "path": "/resources/1"})
    assert resp["statusCode"] == 200
    assert repo.calls["get_resource"]["args"] == (1,)


def test_get_one_not_found_returns_404(repo):
    repo.set("get_resource", None)
    resp = function.handler({"httpMethod": "GET", "path": "/resources/999"})
    assert resp["statusCode"] == 404


def test_get_one_non_numeric_id_returns_404(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/resources/abc"})
    assert resp["statusCode"] == 404


# ---------------------------------------------------------------------------
# POST
# ---------------------------------------------------------------------------

def test_create_valid_returns_201(repo):
    repo.set("create_resource", SAMPLE_RESOURCE)
    event = {"httpMethod": "POST", "path": "/resources",
             "body": json.dumps({"name": "Ada Lovelace", "email": "ada@example.com"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 201
    assert _body(resp)["email"] == "ada@example.com"


def test_create_invalid_returns_400(repo):
    # Missing name and email -> validation fails before the DB is touched.
    event = {"httpMethod": "POST", "path": "/resources", "body": json.dumps({"title": "x"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "details" in _body(resp)


def test_create_duplicate_email_returns_400(repo):
    repo.set("create_resource", DuplicateEmailError("ada@example.com"))
    event = {"httpMethod": "POST", "path": "/resources",
             "body": json.dumps({"name": "Ada", "email": "ada@example.com"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "already exists" in _body(resp)["error"]
    assert "ada@example.com" in _body(resp)["error"]


def test_create_malformed_json_returns_400():
    event = {"httpMethod": "POST", "path": "/resources", "body": "{not json"}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# PUT
# ---------------------------------------------------------------------------

def test_update_valid_returns_200(repo):
    repo.set("get_resource", SAMPLE_RESOURCE)  # before-state fetch for the activity diff
    repo.set("update_resource", SAMPLE_RESOURCE)
    event = {"httpMethod": "PUT", "path": "/resources/1",
             "body": json.dumps({"title": "Staff Engineer"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert repo.calls["update_resource"]["args"][0] == 1


def test_update_not_found_returns_404(repo):
    repo.set("update_resource", None)
    event = {"httpMethod": "PUT", "path": "/resources/999",
             "body": json.dumps({"title": "x"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 404


def test_update_duplicate_email_returns_400(repo):
    repo.set("get_resource", SAMPLE_RESOURCE)  # before-state fetch precedes the update
    repo.set("update_resource", DuplicateEmailError("taken@example.com"))
    event = {"httpMethod": "PUT", "path": "/resources/1",
             "body": json.dumps({"email": "taken@example.com"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "already exists" in _body(resp)["error"]


def test_update_without_id_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/resources", "body": json.dumps({"title": "x"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


def test_update_invalid_payload_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/resources/1",
             "body": json.dumps({"email": "not-an-email"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def test_delete_found_returns_204_with_empty_body(repo):
    repo.set("delete_resource", {"id": 1, "name": "Marcus Reed"})
    resp = function.handler({"httpMethod": "DELETE", "path": "/resources/1"})
    assert resp["statusCode"] == 204
    assert resp["body"] == ""


def test_delete_not_found_returns_404(repo):
    repo.set("delete_resource", None)
    resp = function.handler({"httpMethod": "DELETE", "path": "/resources/999"})
    assert resp["statusCode"] == 404


def test_delete_without_id_returns_400(repo):
    resp = function.handler({"httpMethod": "DELETE", "path": "/resources"})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Cross-cutting / error handling
# ---------------------------------------------------------------------------

def test_unsupported_method_returns_405(repo):
    resp = function.handler({"httpMethod": "PATCH", "path": "/resources/1"})
    assert resp["statusCode"] == 405


def test_repository_error_returns_500(repo):
    repo.set("list_resources", RuntimeError("db down"))
    resp = function.handler({"httpMethod": "GET", "path": "/resources"})
    assert resp["statusCode"] == 500


def test_api_gateway_v2_event_shape(repo):
    repo.set("list_resources", [])
    event = {"requestContext": {"http": {"method": "GET"}}, "rawPath": "/resources"}
    resp = function.handler(event)
    assert resp["statusCode"] == 200


def test_response_serializes_datetime(repo):
    repo.set("get_resource", SAMPLE_RESOURCE)
    resp = function.handler({"httpMethod": "GET", "path": "/resources/1"})
    body = _body(resp)
    assert body["created_at"].startswith("2026-01-01")  # datetime -> ISO string


# ---------------------------------------------------------------------------
# Authentication + RBAC gate
# ---------------------------------------------------------------------------

def _hdr(role):
    token = auth.create_token({"sub": "1", "username": "u", "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_missing_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/resources", "headers": {}})
    assert resp["statusCode"] == 401


def test_invalid_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/resources",
                             "headers": {"Authorization": "Bearer not.a.jwt"}})
    assert resp["statusCode"] == 401


def test_viewer_can_read(repo):
    repo.set("list_resources", [])
    resp = function.handler({"httpMethod": "GET", "path": "/resources", "headers": _hdr("Viewer")})
    assert resp["statusCode"] == 200


def test_viewer_cannot_create_returns_403(repo):
    repo.set("create_resource", SAMPLE_RESOURCE)  # must not be reached
    resp = function.handler({"httpMethod": "POST", "path": "/resources",
                             "headers": _hdr("Viewer"),
                             "body": json.dumps({"name": "X", "email": "x@example.com"})})
    assert resp["statusCode"] == 403
    assert "create_resource" not in repo.calls


def test_contributor_can_create_returns_201(repo):
    repo.set("create_resource", SAMPLE_RESOURCE)
    resp = function.handler({"httpMethod": "POST", "path": "/resources",
                             "headers": _hdr("Contributor"),
                             "body": json.dumps({"name": "X", "email": "x@example.com"})})
    assert resp["statusCode"] == 201


def test_contributor_cannot_delete_returns_403(repo):
    repo.set("delete_resource", {"id": 1})  # must not be reached
    resp = function.handler({"httpMethod": "DELETE", "path": "/resources/1", "headers": _hdr("Contributor")})
    assert resp["statusCode"] == 403
    assert "delete_resource" not in repo.calls


def test_manager_can_delete_returns_204(repo):
    repo.set("delete_resource", {"id": 1, "name": "Marcus Reed"})
    resp = function.handler({"httpMethod": "DELETE", "path": "/resources/1", "headers": _hdr("Manager")})
    assert resp["statusCode"] == 204


def test_deleted_user_token_returns_401(repo, monkeypatch):
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: False)
    resp = function.handler({"httpMethod": "GET", "path": "/resources", "headers": _hdr("Admin")})
    assert resp["statusCode"] == 401


def test_bogus_role_token_returns_403(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/resources", "headers": _hdr("Wizard")})
    assert resp["statusCode"] == 403


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def test_list_custom_pagination_passed(repo):
    repo.set("list_resources", {"items": [], "total": 0, "limit": 5, "offset": 15})
    function.handler({"httpMethod": "GET", "path": "/resources",
                      "queryStringParameters": {"limit": "5", "offset": "15"}})
    assert repo.calls["list_resources"]["kwargs"]["limit"] == 5
    assert repo.calls["list_resources"]["kwargs"]["offset"] == 15


def test_list_limit_capped_at_max(repo):
    repo.set("list_resources", {"items": [], "total": 0, "limit": 200, "offset": 0})
    function.handler({"httpMethod": "GET", "path": "/resources",
                      "queryStringParameters": {"limit": "99999"}})
    assert repo.calls["list_resources"]["kwargs"]["limit"] == 200


def test_list_invalid_limit_returns_400(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/resources",
                             "queryStringParameters": {"limit": "ten"}})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Input robustness
# ---------------------------------------------------------------------------

def test_whitespace_only_name_returns_400(repo):
    resp = function.handler({"httpMethod": "POST", "path": "/resources",
                             "body": json.dumps({"name": "   ", "email": "a@b.com"})})
    assert resp["statusCode"] == 400
    assert "create_resource" not in repo.calls


def test_overlong_name_returns_400_not_500(repo):
    resp = function.handler({"httpMethod": "POST", "path": "/resources",
                             "body": json.dumps({"name": "x" * 10000, "email": "a@b.com"})})
    assert resp["statusCode"] == 400
    assert "create_resource" not in repo.calls


def test_sql_injection_name_is_treated_as_data(repo):
    repo.set("create_resource", SAMPLE_RESOURCE)
    payload = "'; DROP TABLE resources;--"
    resp = function.handler({"httpMethod": "POST", "path": "/resources",
                             "body": json.dumps({"name": payload, "email": "a@b.com"})})
    assert resp["statusCode"] == 201
    assert repo.calls["create_resource"]["args"][0]["name"] == payload
