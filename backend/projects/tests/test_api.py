"""
API tests — the function.handler router with the repository mocked (via the
shared `repo` fixture). Covers routing, status codes, request parsing, pagination
plumbing, and response shaping. Authentication is supplied by the autouse Admin
injection; permission behaviour lives in test_security.py.
"""

import json
from datetime import date
from decimal import Decimal

import pytest

import function
from testkit import parse_body

pytestmark = pytest.mark.api


SAMPLE_PROJECT = {
    "id": 1, "name": "Apollo", "description": "Moon program", "status": "active",
    "department": "R&D", "start_date": date(2026, 1, 1), "end_date": date(2026, 12, 31),
    "deadline": date(2026, 11, 30), "budget_planned": Decimal("1000000.00"),
    "budget_consumed": Decimal("250000.50"),
}


# ---------------------------------------------------------------------------
# GET (list + item)
# ---------------------------------------------------------------------------

def test_list_returns_200_and_passes_filters(repo):
    repo.set("list_projects", {"items": [SAMPLE_PROJECT], "total": 1, "limit": 50, "offset": 0})
    resp = function.handler({
        "httpMethod": "GET", "path": "/projects",
        "queryStringParameters": {"status": "active", "department": "R&D"},
    })
    assert resp["statusCode"] == 200
    body = parse_body(resp)
    assert body["items"][0]["name"] == "Apollo"
    assert body["total"] == 1 and body["limit"] == 50 and body["offset"] == 0
    assert repo.calls["list_projects"]["kwargs"] == {
        "status": "active", "department": "R&D", "search": None, "limit": 50, "offset": 0,
    }


def test_list_passes_search_and_combines_with_filters(repo):
    repo.set("list_projects", {"items": [SAMPLE_PROJECT], "total": 1, "limit": 50, "offset": 0})
    resp = function.handler({
        "httpMethod": "GET", "path": "/projects",
        "queryStringParameters": {"status": "active", "search": "  apollo  "},
    })
    assert resp["statusCode"] == 200
    assert repo.calls["list_projects"]["kwargs"]["search"] == "apollo"  # trimmed
    assert repo.calls["list_projects"]["kwargs"]["status"] == "active"


def test_list_with_overlong_search_returns_400(repo):
    resp = function.handler({
        "httpMethod": "GET", "path": "/projects", "queryStringParameters": {"search": "x" * 201},
    })
    assert resp["statusCode"] == 400


def test_get_existing_project_returns_200(repo):
    repo.set("get_project", SAMPLE_PROJECT)
    resp = function.handler({"httpMethod": "GET", "path": "/projects/1"})
    assert resp["statusCode"] == 200
    assert repo.calls["get_project"]["args"] == (1,)


def test_get_missing_project_returns_404(repo):
    repo.set("get_project", None)
    resp = function.handler({"httpMethod": "GET", "path": "/projects/999"})
    assert resp["statusCode"] == 404


def test_get_with_non_numeric_id_returns_404(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/projects/abc"})
    assert resp["statusCode"] == 404


def test_get_uses_path_parameters_when_present(repo):
    repo.set("get_project", SAMPLE_PROJECT)
    resp = function.handler({"httpMethod": "GET", "pathParameters": {"id": "1"}})
    assert resp["statusCode"] == 200
    assert repo.calls["get_project"]["args"] == (1,)


# ---------------------------------------------------------------------------
# POST (create)
# ---------------------------------------------------------------------------

def test_create_valid_returns_201(repo):
    repo.set("create_project", SAMPLE_PROJECT)
    resp = function.handler({"httpMethod": "POST", "path": "/projects", "body": json.dumps({"name": "Apollo"})})
    assert resp["statusCode"] == 201
    assert parse_body(resp)["name"] == "Apollo"


def test_create_with_invalid_payload_returns_400(repo):
    # Validation fails before the DB is touched.
    resp = function.handler({"httpMethod": "POST", "path": "/projects", "body": json.dumps({"description": "no name"})})
    assert resp["statusCode"] == 400
    assert "details" in parse_body(resp)


def test_create_with_malformed_json_returns_400():
    resp = function.handler({"httpMethod": "POST", "path": "/projects", "body": "{not json"})
    assert resp["statusCode"] == 400


def test_create_accepts_an_already_parsed_dict_body(repo):
    repo.set("create_project", SAMPLE_PROJECT)
    resp = function.handler({"httpMethod": "POST", "path": "/projects", "body": {"name": "Apollo"}})
    assert resp["statusCode"] == 201


# ---------------------------------------------------------------------------
# PUT (update)
# ---------------------------------------------------------------------------

def test_update_valid_returns_200(repo):
    repo.set("get_project", SAMPLE_PROJECT)  # before-state fetch for the activity diff
    repo.set("update_project", SAMPLE_PROJECT)
    resp = function.handler({"httpMethod": "PUT", "path": "/projects/1", "body": json.dumps({"status": "completed"})})
    assert resp["statusCode"] == 200
    assert repo.calls["update_project"]["args"][0] == 1


def test_update_missing_project_returns_404(repo):
    repo.set("update_project", None)
    resp = function.handler({"httpMethod": "PUT", "path": "/projects/999", "body": json.dumps({"status": "completed"})})
    assert resp["statusCode"] == 404


def test_update_without_id_returns_400(repo):
    resp = function.handler({"httpMethod": "PUT", "path": "/projects", "body": json.dumps({"status": "completed"})})
    assert resp["statusCode"] == 400


def test_update_with_invalid_status_returns_400(repo):
    resp = function.handler({"httpMethod": "PUT", "path": "/projects/1", "body": json.dumps({"status": "archived"})})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def test_delete_existing_project_returns_204_with_empty_body(repo):
    repo.set("delete_project", {"id": 1, "name": "Apollo"})
    resp = function.handler({"httpMethod": "DELETE", "path": "/projects/1"})
    assert resp["statusCode"] == 204
    assert resp["body"] == ""


def test_delete_missing_project_returns_404(repo):
    repo.set("delete_project", None)
    resp = function.handler({"httpMethod": "DELETE", "path": "/projects/999"})
    assert resp["statusCode"] == 404


def test_delete_without_id_returns_400(repo):
    resp = function.handler({"httpMethod": "DELETE", "path": "/projects"})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Cross-cutting: methods, errors, event shapes, serialization
# ---------------------------------------------------------------------------

def test_unsupported_method_returns_405(repo):
    resp = function.handler({"httpMethod": "PATCH", "path": "/projects/1"})
    assert resp["statusCode"] == 405


def test_repository_error_returns_500(repo):
    repo.set("list_projects", RuntimeError("db down"))
    resp = function.handler({"httpMethod": "GET", "path": "/projects"})
    assert resp["statusCode"] == 500


def test_accepts_api_gateway_v2_event_shape(repo):
    repo.set("list_projects", [])
    resp = function.handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/projects"})
    assert resp["statusCode"] == 200


def test_response_serializes_dates_and_decimals(repo):
    repo.set("get_project", SAMPLE_PROJECT)
    body = parse_body(function.handler({"httpMethod": "GET", "path": "/projects/1"}))
    assert body["start_date"] == "2026-01-01"       # date -> ISO string
    assert body["budget_planned"] == 1000000.0      # Decimal -> float


# ---------------------------------------------------------------------------
# Pagination plumbing
# ---------------------------------------------------------------------------

def test_list_passes_default_pagination(repo):
    repo.set("list_projects", {"items": [], "total": 0, "limit": 50, "offset": 0})
    function.handler({"httpMethod": "GET", "path": "/projects"})
    assert repo.calls["list_projects"]["kwargs"]["limit"] == 50
    assert repo.calls["list_projects"]["kwargs"]["offset"] == 0


def test_list_passes_custom_pagination(repo):
    repo.set("list_projects", {"items": [], "total": 0, "limit": 10, "offset": 20})
    function.handler({"httpMethod": "GET", "path": "/projects", "queryStringParameters": {"limit": "10", "offset": "20"}})
    assert repo.calls["list_projects"]["kwargs"]["limit"] == 10
    assert repo.calls["list_projects"]["kwargs"]["offset"] == 20


def test_list_caps_limit_at_maximum(repo):
    repo.set("list_projects", {"items": [], "total": 0, "limit": 200, "offset": 0})
    function.handler({"httpMethod": "GET", "path": "/projects", "queryStringParameters": {"limit": "99999"}})
    assert repo.calls["list_projects"]["kwargs"]["limit"] == 200


def test_list_with_invalid_limit_returns_400(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/projects", "queryStringParameters": {"limit": "abc"}})
    assert resp["statusCode"] == 400


def test_list_with_negative_offset_returns_400(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/projects", "queryStringParameters": {"offset": "-1"}})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Input robustness (validation at the boundary)
# ---------------------------------------------------------------------------

def test_create_with_whitespace_only_name_returns_400(repo):
    resp = function.handler({"httpMethod": "POST", "path": "/projects", "body": json.dumps({"name": "   "})})
    assert resp["statusCode"] == 400
    assert "create_project" not in repo.calls


def test_create_with_overlong_name_returns_400_not_500(repo):
    resp = function.handler({"httpMethod": "POST", "path": "/projects", "body": json.dumps({"name": "x" * 10000})})
    assert resp["statusCode"] == 400
    assert "create_project" not in repo.calls
