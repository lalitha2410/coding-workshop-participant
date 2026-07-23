"""
API tests — the function.handler router with the repository mocked (via the
shared `repo` fixture). Covers routing, status codes, request parsing, pagination
plumbing, duplicate-email handling, and response shaping. Authentication is
supplied by the autouse Admin injection; permission behaviour lives in
test_security.py.
"""

import json
from datetime import datetime

import pytest

import function
from resources_repository import DuplicateEmailError
from testkit import parse_body

pytestmark = pytest.mark.api


SAMPLE_RESOURCE = {
    "id": 1,
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "title": "Principal Engineer",
    "created_at": datetime(2026, 1, 1, 12, 0, 0),
}


# ---------------------------------------------------------------------------
# GET (list + item)
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
    body = parse_body(resp)
    assert body["items"][0]["name"] == "Ada Lovelace"
    assert body["total"] == 1 and body["limit"] == 50 and body["offset"] == 0
    assert repo.calls["list_resources"]["kwargs"] == {"search": "ada", "limit": 50, "offset": 0}


def test_list_without_search_passes_none(repo):
    repo.set("list_resources", {"items": [], "total": 0, "limit": 50, "offset": 0})
    resp = function.handler({"httpMethod": "GET", "path": "/resources"})
    assert resp["statusCode"] == 200
    assert repo.calls["list_resources"]["kwargs"] == {"search": None, "limit": 50, "offset": 0}


def test_get_existing_resource_returns_200(repo):
    repo.set("get_resource", SAMPLE_RESOURCE)
    resp = function.handler({"httpMethod": "GET", "path": "/resources/1"})
    assert resp["statusCode"] == 200
    assert repo.calls["get_resource"]["args"] == (1,)


def test_get_missing_resource_returns_404(repo):
    repo.set("get_resource", None)
    resp = function.handler({"httpMethod": "GET", "path": "/resources/999"})
    assert resp["statusCode"] == 404


def test_get_with_non_numeric_id_returns_404(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/resources/abc"})
    assert resp["statusCode"] == 404


# ---------------------------------------------------------------------------
# POST (create)
# ---------------------------------------------------------------------------

def test_create_valid_returns_201(repo):
    repo.set("create_resource", SAMPLE_RESOURCE)
    event = {"httpMethod": "POST", "path": "/resources",
             "body": json.dumps({"name": "Ada Lovelace", "email": "ada@example.com"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 201
    assert parse_body(resp)["email"] == "ada@example.com"


def test_create_with_invalid_payload_returns_400(repo):
    # Missing name and email -> validation fails before the DB is touched.
    event = {"httpMethod": "POST", "path": "/resources", "body": json.dumps({"title": "x"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "details" in parse_body(resp)


def test_create_duplicate_email_returns_400(repo):
    repo.set("create_resource", DuplicateEmailError("ada@example.com"))
    event = {"httpMethod": "POST", "path": "/resources",
             "body": json.dumps({"name": "Ada", "email": "ada@example.com"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "already exists" in parse_body(resp)["error"]
    assert "ada@example.com" in parse_body(resp)["error"]


def test_create_with_malformed_json_returns_400():
    event = {"httpMethod": "POST", "path": "/resources", "body": "{not json"}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# PUT (update)
# ---------------------------------------------------------------------------

def test_update_valid_returns_200(repo):
    repo.set("get_resource", SAMPLE_RESOURCE)  # before-state fetch for the activity diff
    repo.set("update_resource", SAMPLE_RESOURCE)
    event = {"httpMethod": "PUT", "path": "/resources/1",
             "body": json.dumps({"title": "Staff Engineer"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert repo.calls["update_resource"]["args"][0] == 1


def test_update_missing_resource_returns_404(repo):
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
    assert "already exists" in parse_body(resp)["error"]


def test_update_without_id_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/resources", "body": json.dumps({"title": "x"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


def test_update_with_invalid_payload_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/resources/1",
             "body": json.dumps({"email": "not-an-email"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def test_delete_existing_resource_returns_204_with_empty_body(repo):
    repo.set("delete_resource", {"id": 1, "name": "Marcus Reed"})
    resp = function.handler({"httpMethod": "DELETE", "path": "/resources/1"})
    assert resp["statusCode"] == 204
    assert resp["body"] == ""


def test_delete_missing_resource_returns_404(repo):
    repo.set("delete_resource", None)
    resp = function.handler({"httpMethod": "DELETE", "path": "/resources/999"})
    assert resp["statusCode"] == 404


def test_delete_without_id_returns_400(repo):
    resp = function.handler({"httpMethod": "DELETE", "path": "/resources"})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Cross-cutting: methods, errors, event shapes, serialization
# ---------------------------------------------------------------------------

def test_unsupported_method_returns_405(repo):
    resp = function.handler({"httpMethod": "PATCH", "path": "/resources/1"})
    assert resp["statusCode"] == 405


def test_repository_error_returns_500(repo):
    repo.set("list_resources", RuntimeError("db down"))
    resp = function.handler({"httpMethod": "GET", "path": "/resources"})
    assert resp["statusCode"] == 500


def test_accepts_api_gateway_v2_event_shape(repo):
    repo.set("list_resources", [])
    event = {"requestContext": {"http": {"method": "GET"}}, "rawPath": "/resources"}
    resp = function.handler(event)
    assert resp["statusCode"] == 200


def test_response_serializes_datetime(repo):
    repo.set("get_resource", SAMPLE_RESOURCE)
    resp = function.handler({"httpMethod": "GET", "path": "/resources/1"})
    body = parse_body(resp)
    assert body["created_at"].startswith("2026-01-01")  # datetime -> ISO string


# ---------------------------------------------------------------------------
# Pagination plumbing
# ---------------------------------------------------------------------------

def test_list_passes_custom_pagination(repo):
    repo.set("list_resources", {"items": [], "total": 0, "limit": 5, "offset": 15})
    function.handler({"httpMethod": "GET", "path": "/resources",
                      "queryStringParameters": {"limit": "5", "offset": "15"}})
    assert repo.calls["list_resources"]["kwargs"]["limit"] == 5
    assert repo.calls["list_resources"]["kwargs"]["offset"] == 15


def test_list_caps_limit_at_maximum(repo):
    repo.set("list_resources", {"items": [], "total": 0, "limit": 200, "offset": 0})
    function.handler({"httpMethod": "GET", "path": "/resources",
                      "queryStringParameters": {"limit": "99999"}})
    assert repo.calls["list_resources"]["kwargs"]["limit"] == 200


def test_list_with_invalid_limit_returns_400(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/resources",
                             "queryStringParameters": {"limit": "ten"}})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Input robustness (validation at the boundary)
# ---------------------------------------------------------------------------

def test_create_with_whitespace_only_name_returns_400(repo):
    resp = function.handler({"httpMethod": "POST", "path": "/resources",
                             "body": json.dumps({"name": "   ", "email": "a@b.com"})})
    assert resp["statusCode"] == 400
    assert "create_resource" not in repo.calls


def test_create_with_overlong_name_returns_400_not_500(repo):
    resp = function.handler({"httpMethod": "POST", "path": "/resources",
                             "body": json.dumps({"name": "x" * 10000, "email": "a@b.com"})})
    assert resp["statusCode"] == 400
    assert "create_resource" not in repo.calls
