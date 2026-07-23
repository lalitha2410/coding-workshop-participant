"""
API tests — the function.handler router with the repository mocked (via the
shared `repo` fixture). Covers routing, status codes, request parsing, the
dual-FK reference guard, duplicate handling, the analytics routes, pagination
plumbing, and response shaping. Authentication is supplied by the autouse Admin
injection; permission behaviour lives in test_security.py.
"""

import json
from datetime import date

import pytest

import function
from testkit import parse_body
from allocations_repository import DuplicateAllocationError

pytestmark = pytest.mark.api


SAMPLE_ALLOCATION = {
    "id": 1,
    "resource_id": 10,
    "project_id": 20,
    "allocation_pct": 50,
    "start_date": date(2026, 1, 1),
    "end_date": date(2026, 6, 30),
}

OVER = [{
    "resource_id": 10, "resource_name": "Ada", "email": "ada@x.com",
    "total_allocation_pct": 150, "project_count": 2, "over_allocated": True,
}]


@pytest.fixture(autouse=True)
def _references_exist(monkeypatch):
    """By default both referenced rows exist, so create/update reach the DB layer.
    Tests that assert the dual-FK guard override these per-test."""
    monkeypatch.setattr(function, "resource_exists", lambda rid: True)
    monkeypatch.setattr(function, "project_exists", lambda pid: True)


# ---------------------------------------------------------------------------
# GET (list / get)
# ---------------------------------------------------------------------------

def test_list_returns_200_and_passes_filters(repo):
    repo.set("list_allocations", {"items": [SAMPLE_ALLOCATION], "total": 1, "limit": 50, "offset": 0})
    event = {
        "httpMethod": "GET",
        "path": "/allocations",
        "queryStringParameters": {"resource_id": "10", "project_id": "20"},
    }
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    body = parse_body(resp)
    assert body["items"][0]["id"] == 1
    assert body["total"] == 1 and body["limit"] == 50 and body["offset"] == 0
    assert repo.calls["list_allocations"]["kwargs"] == {
        "resource_id": "10", "project_id": "20", "search": None, "limit": 50, "offset": 0,
    }


def test_list_passes_search_and_combines_with_filters(repo):
    repo.set("list_allocations", {"items": [SAMPLE_ALLOCATION], "total": 1, "limit": 50, "offset": 0})
    resp = function.handler({
        "httpMethod": "GET", "path": "/allocations",
        "queryStringParameters": {"resource_id": "10", "search": "  marcus  "},
    })
    assert resp["statusCode"] == 200
    assert repo.calls["list_allocations"]["kwargs"]["search"] == "marcus"
    assert repo.calls["list_allocations"]["kwargs"]["resource_id"] == "10"


def test_list_with_overlong_search_returns_400(repo):
    resp = function.handler({
        "httpMethod": "GET", "path": "/allocations",
        "queryStringParameters": {"search": "x" * 201},
    })
    assert resp["statusCode"] == 400


def test_get_existing_allocation_returns_200(repo):
    repo.set("get_allocation", SAMPLE_ALLOCATION)
    resp = function.handler({"httpMethod": "GET", "path": "/allocations/1"})
    assert resp["statusCode"] == 200
    assert repo.calls["get_allocation"]["args"] == (1,)


def test_get_missing_allocation_returns_404(repo):
    repo.set("get_allocation", None)
    resp = function.handler({"httpMethod": "GET", "path": "/allocations/999"})
    assert resp["statusCode"] == 404


def test_get_with_non_numeric_id_returns_404(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/allocations/abc"})
    assert resp["statusCode"] == 404


# ---------------------------------------------------------------------------
# Analytics routes
# ---------------------------------------------------------------------------

def test_over_allocated_route_returns_over_only_totals(repo):
    repo.set("resource_allocation_totals", OVER)
    resp = function.handler({"httpMethod": "GET", "path": "/allocations/over-allocated"})
    assert resp["statusCode"] == 200
    assert repo.calls["resource_allocation_totals"]["kwargs"] == {"over_only": True}
    assert parse_body(resp)[0]["over_allocated"] is True


def test_summary_route_returns_all_totals(repo):
    repo.set("resource_allocation_totals", OVER)
    resp = function.handler({"httpMethod": "GET", "path": "/allocations/summary"})
    assert resp["statusCode"] == 200
    assert repo.calls["resource_allocation_totals"]["kwargs"] == {"over_only": False}


def test_over_allocated_route_accepts_api_gateway_v2_event_shape(repo):
    repo.set("resource_allocation_totals", [])
    event = {"requestContext": {"http": {"method": "GET"}}, "rawPath": "/allocations/over-allocated"}
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert repo.calls["resource_allocation_totals"]["kwargs"] == {"over_only": True}


# ---------------------------------------------------------------------------
# POST — including the dual-FK guard and duplicate handling
# ---------------------------------------------------------------------------

def test_create_valid_returns_201(repo):
    repo.set("create_allocation", SAMPLE_ALLOCATION)
    event = {"httpMethod": "POST", "path": "/allocations",
             "body": json.dumps({"resource_id": 10, "project_id": 20, "allocation_pct": 50})}
    resp = function.handler(event)
    assert resp["statusCode"] == 201


def test_create_with_invalid_payload_returns_400(repo):
    event = {"httpMethod": "POST", "path": "/allocations", "body": json.dumps({"allocation_pct": 50})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "details" in parse_body(resp)


def test_create_with_missing_resource_returns_400(repo, monkeypatch):
    monkeypatch.setattr(function, "resource_exists", lambda rid: False)
    repo.set("create_allocation", SAMPLE_ALLOCATION)  # must not be called
    event = {"httpMethod": "POST", "path": "/allocations",
             "body": json.dumps({"resource_id": 9999, "project_id": 20})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "resource 9999" in parse_body(resp)["error"]
    assert "create_allocation" not in repo.calls


def test_create_with_missing_project_returns_400(repo, monkeypatch):
    monkeypatch.setattr(function, "project_exists", lambda pid: False)
    repo.set("create_allocation", SAMPLE_ALLOCATION)
    event = {"httpMethod": "POST", "path": "/allocations",
             "body": json.dumps({"resource_id": 10, "project_id": 9999})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "project 9999" in parse_body(resp)["error"]


def test_create_with_both_references_missing_reports_both(repo, monkeypatch):
    monkeypatch.setattr(function, "resource_exists", lambda rid: False)
    monkeypatch.setattr(function, "project_exists", lambda pid: False)
    event = {"httpMethod": "POST", "path": "/allocations",
             "body": json.dumps({"resource_id": 8, "project_id": 9})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    err = parse_body(resp)["error"]
    assert "resource 8" in err and "project 9" in err


def test_create_with_duplicate_pair_returns_400(repo):
    repo.set("create_allocation", DuplicateAllocationError(10, 20))
    event = {"httpMethod": "POST", "path": "/allocations",
             "body": json.dumps({"resource_id": 10, "project_id": 20})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "already allocated" in parse_body(resp)["error"]


def test_create_with_malformed_json_returns_400():
    event = {"httpMethod": "POST", "path": "/allocations", "body": "{nope"}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# PUT
# ---------------------------------------------------------------------------

def test_update_valid_returns_200(repo):
    repo.set("get_allocation", SAMPLE_ALLOCATION)  # before-state fetch for the activity diff
    repo.set("update_allocation", SAMPLE_ALLOCATION)
    event = {"httpMethod": "PUT", "path": "/allocations/1",
             "body": json.dumps({"allocation_pct": 75})}
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert repo.calls["update_allocation"]["args"][0] == 1


def test_update_missing_allocation_returns_404(repo):
    repo.set("update_allocation", None)
    event = {"httpMethod": "PUT", "path": "/allocations/999",
             "body": json.dumps({"allocation_pct": 75})}
    resp = function.handler(event)
    assert resp["statusCode"] == 404


def test_update_with_missing_reference_returns_400(repo, monkeypatch):
    monkeypatch.setattr(function, "project_exists", lambda pid: False)
    repo.set("update_allocation", SAMPLE_ALLOCATION)  # must not be called
    event = {"httpMethod": "PUT", "path": "/allocations/1",
             "body": json.dumps({"project_id": 9999})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "update_allocation" not in repo.calls


def test_update_with_duplicate_pair_returns_400(repo):
    repo.set("get_allocation", SAMPLE_ALLOCATION)  # before-state fetch precedes the update
    repo.set("update_allocation", DuplicateAllocationError(10, 20))
    event = {"httpMethod": "PUT", "path": "/allocations/1",
             "body": json.dumps({"resource_id": 10, "project_id": 20})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "already allocated" in parse_body(resp)["error"]


def test_update_without_id_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/allocations", "body": json.dumps({"allocation_pct": 75})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


def test_update_with_invalid_payload_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/allocations/1",
             "body": json.dumps({"allocation_pct": 500})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def test_delete_existing_allocation_returns_204_with_empty_body(repo):
    repo.set("delete_allocation", {"id": 1, "resource_id": 10, "project_id": 20})
    resp = function.handler({"httpMethod": "DELETE", "path": "/allocations/1"})
    assert resp["statusCode"] == 204
    assert resp["body"] == ""


def test_delete_missing_allocation_returns_404(repo):
    repo.set("delete_allocation", None)
    resp = function.handler({"httpMethod": "DELETE", "path": "/allocations/999"})
    assert resp["statusCode"] == 404


def test_delete_without_id_returns_400(repo):
    resp = function.handler({"httpMethod": "DELETE", "path": "/allocations"})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Cross-cutting / error handling
# ---------------------------------------------------------------------------

def test_unsupported_method_returns_405(repo):
    resp = function.handler({"httpMethod": "PATCH", "path": "/allocations/1"})
    assert resp["statusCode"] == 405


def test_repository_error_returns_500(repo):
    repo.set("list_allocations", RuntimeError("db down"))
    resp = function.handler({"httpMethod": "GET", "path": "/allocations"})
    assert resp["statusCode"] == 500


def test_response_serializes_dates(repo):
    repo.set("get_allocation", SAMPLE_ALLOCATION)
    resp = function.handler({"httpMethod": "GET", "path": "/allocations/1"})
    body = parse_body(resp)
    assert body["start_date"] == "2026-01-01"
    assert body["end_date"] == "2026-06-30"


# ---------------------------------------------------------------------------
# Pagination (list endpoint; analytics endpoints are unpaginated summaries)
# ---------------------------------------------------------------------------

def test_list_passes_custom_pagination(repo):
    repo.set("list_allocations", {"items": [], "total": 0, "limit": 3, "offset": 6})
    function.handler({"httpMethod": "GET", "path": "/allocations",
                      "queryStringParameters": {"limit": "3", "offset": "6"}})
    assert repo.calls["list_allocations"]["kwargs"]["limit"] == 3
    assert repo.calls["list_allocations"]["kwargs"]["offset"] == 6


def test_list_caps_limit_at_maximum(repo):
    repo.set("list_allocations", {"items": [], "total": 0, "limit": 200, "offset": 0})
    function.handler({"httpMethod": "GET", "path": "/allocations",
                      "queryStringParameters": {"limit": "99999"}})
    assert repo.calls["list_allocations"]["kwargs"]["limit"] == 200


def test_list_with_invalid_limit_returns_400(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/allocations",
                             "queryStringParameters": {"limit": "-4"}})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Input robustness (allocations has no string columns; ids/dates only)
# ---------------------------------------------------------------------------

def test_create_with_whitespace_only_resource_id_returns_400(repo):
    resp = function.handler({"httpMethod": "POST", "path": "/allocations",
                             "body": json.dumps({"resource_id": "   ", "project_id": 20})})
    assert resp["statusCode"] == 400
    assert "create_allocation" not in repo.calls


def test_create_with_overlong_date_string_returns_400_not_500(repo):
    # A huge/garbage string in a date field is rejected cleanly, never a 500.
    resp = function.handler({"httpMethod": "POST", "path": "/allocations",
                             "body": json.dumps({"resource_id": 10, "project_id": 20,
                                                  "start_date": "x" * 10000})})
    assert resp["statusCode"] == 400
    assert "create_allocation" not in repo.calls
