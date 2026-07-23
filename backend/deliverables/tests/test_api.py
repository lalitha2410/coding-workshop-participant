"""
API tests — the function.handler router with the repository mocked (via the
shared `repo` fixture). Covers routing, status codes, request parsing, pagination
plumbing, response shaping, and the dependency routes. Authentication is supplied
by the autouse Admin injection; permission behaviour lives in test_security.py.
"""

import json
from datetime import date

import pytest

import function
from testkit import parse_body
from deliverables_repository import DuplicateDependencyError

pytestmark = pytest.mark.api


SAMPLE_DELIVERABLE = {
    "id": 1,
    "project_id": 10,
    "name": "Design doc",
    "description": "Architecture write-up",
    "status": "in_progress",
    "completion_pct": 40,
    "due_date": date(2026, 6, 30),
    "created_at": date(2026, 1, 1),
    "updated_at": date(2026, 1, 2),
}


@pytest.fixture(autouse=True)
def _project_exists_true(monkeypatch):
    """Referenced project exists by default so create/update reach the DB layer;
    tests asserting the missing-project path override this themselves."""
    monkeypatch.setattr(function, "project_exists", lambda pid: True)


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------

def test_list_returns_200_and_passes_filters(repo):
    repo.set("list_deliverables", {"items": [SAMPLE_DELIVERABLE], "total": 1, "limit": 50, "offset": 0})
    event = {
        "httpMethod": "GET",
        "path": "/deliverables",
        "queryStringParameters": {"project_id": "10", "status": "in_progress"},
    }
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    body = parse_body(resp)
    assert body["items"][0]["name"] == "Design doc"
    assert body["total"] == 1 and body["limit"] == 50 and body["offset"] == 0
    assert repo.calls["list_deliverables"]["kwargs"] == {
        "project_id": "10", "status": "in_progress", "search": None, "limit": 50, "offset": 0,
    }


def test_list_passes_search_and_combines_with_filters(repo):
    repo.set("list_deliverables", {"items": [SAMPLE_DELIVERABLE], "total": 1, "limit": 50, "offset": 0})
    resp = function.handler({
        "httpMethod": "GET", "path": "/deliverables",
        "queryStringParameters": {"project_id": "10", "search": "  design  "},
    })
    assert resp["statusCode"] == 200
    assert repo.calls["list_deliverables"]["kwargs"]["search"] == "design"
    assert repo.calls["list_deliverables"]["kwargs"]["project_id"] == "10"


def test_list_with_overlong_search_returns_400(repo):
    resp = function.handler({
        "httpMethod": "GET", "path": "/deliverables",
        "queryStringParameters": {"search": "x" * 201},
    })
    assert resp["statusCode"] == 400


def test_get_existing_deliverable_returns_200(repo):
    repo.set("get_deliverable", SAMPLE_DELIVERABLE)
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables/1"})
    assert resp["statusCode"] == 200
    assert repo.calls["get_deliverable"]["args"] == (1,)


def test_get_missing_deliverable_returns_404(repo):
    repo.set("get_deliverable", None)
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables/999"})
    assert resp["statusCode"] == 404


def test_get_with_non_numeric_id_returns_404(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables/abc"})
    assert resp["statusCode"] == 404


# ---------------------------------------------------------------------------
# POST
# ---------------------------------------------------------------------------

def test_create_valid_returns_201(repo):
    repo.set("create_deliverable", SAMPLE_DELIVERABLE)
    event = {"httpMethod": "POST", "path": "/deliverables",
             "body": json.dumps({"project_id": 10, "name": "Design doc"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 201
    assert parse_body(resp)["name"] == "Design doc"


def test_create_with_invalid_payload_returns_400(repo):
    # Missing project_id and name -> validation fails before the DB is touched.
    event = {"httpMethod": "POST", "path": "/deliverables", "body": json.dumps({"description": "x"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "details" in parse_body(resp)


def test_create_with_missing_project_returns_400(repo, monkeypatch):
    # Payload is valid, but the referenced project does not exist.
    monkeypatch.setattr(function, "project_exists", lambda pid: False)
    repo.set("create_deliverable", SAMPLE_DELIVERABLE)  # should never be called
    event = {"httpMethod": "POST", "path": "/deliverables",
             "body": json.dumps({"project_id": 9999, "name": "Orphan"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "does not exist" in parse_body(resp)["error"]
    assert "create_deliverable" not in repo.calls


def test_create_with_malformed_json_returns_400():
    event = {"httpMethod": "POST", "path": "/deliverables", "body": "{not json"}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# PUT
# ---------------------------------------------------------------------------

def test_update_valid_returns_200(repo):
    repo.set("get_deliverable", SAMPLE_DELIVERABLE)  # before-state fetch for the activity diff
    repo.set("update_deliverable", SAMPLE_DELIVERABLE)
    event = {"httpMethod": "PUT", "path": "/deliverables/1",
             "body": json.dumps({"status": "completed"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert repo.calls["update_deliverable"]["args"][0] == 1


def test_update_missing_deliverable_returns_404(repo):
    repo.set("update_deliverable", None)
    event = {"httpMethod": "PUT", "path": "/deliverables/999",
             "body": json.dumps({"status": "completed"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 404


def test_update_with_missing_project_returns_400(repo, monkeypatch):
    monkeypatch.setattr(function, "project_exists", lambda pid: False)
    repo.set("update_deliverable", SAMPLE_DELIVERABLE)  # should never be called
    event = {"httpMethod": "PUT", "path": "/deliverables/1",
             "body": json.dumps({"project_id": 9999})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "update_deliverable" not in repo.calls


def test_update_without_id_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/deliverables", "body": json.dumps({"status": "completed"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


def test_update_with_invalid_payload_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/deliverables/1",
             "body": json.dumps({"completion_pct": 500})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def test_delete_existing_deliverable_returns_204_with_empty_body(repo):
    repo.set("delete_deliverable", {"id": 1, "name": "Beta"})
    resp = function.handler({"httpMethod": "DELETE", "path": "/deliverables/1"})
    assert resp["statusCode"] == 204
    assert resp["body"] == ""


def test_delete_missing_deliverable_returns_404(repo):
    repo.set("delete_deliverable", None)
    resp = function.handler({"httpMethod": "DELETE", "path": "/deliverables/999"})
    assert resp["statusCode"] == 404


def test_delete_without_id_returns_400(repo):
    resp = function.handler({"httpMethod": "DELETE", "path": "/deliverables"})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Cross-cutting / error handling
# ---------------------------------------------------------------------------

def test_unsupported_method_returns_405(repo):
    resp = function.handler({"httpMethod": "PATCH", "path": "/deliverables/1"})
    assert resp["statusCode"] == 405


def test_repository_error_returns_500(repo):
    repo.set("list_deliverables", RuntimeError("db down"))
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables"})
    assert resp["statusCode"] == 500


def test_accepts_api_gateway_v2_event_shape(repo):
    repo.set("list_deliverables", [])
    event = {"requestContext": {"http": {"method": "GET"}}, "rawPath": "/deliverables"}
    resp = function.handler(event)
    assert resp["statusCode"] == 200


def test_response_serializes_dates(repo):
    repo.set("get_deliverable", SAMPLE_DELIVERABLE)
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables/1"})
    body = parse_body(resp)
    assert body["due_date"] == "2026-06-30"  # date -> ISO string


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def test_list_passes_custom_pagination(repo):
    repo.set("list_deliverables", {"items": [], "total": 0, "limit": 10, "offset": 20})
    function.handler({"httpMethod": "GET", "path": "/deliverables",
                      "queryStringParameters": {"limit": "10", "offset": "20"}})
    assert repo.calls["list_deliverables"]["kwargs"]["limit"] == 10
    assert repo.calls["list_deliverables"]["kwargs"]["offset"] == 20


def test_list_caps_limit_at_maximum(repo):
    repo.set("list_deliverables", {"items": [], "total": 0, "limit": 200, "offset": 0})
    function.handler({"httpMethod": "GET", "path": "/deliverables",
                      "queryStringParameters": {"limit": "99999"}})
    assert repo.calls["list_deliverables"]["kwargs"]["limit"] == 200


def test_list_with_invalid_offset_returns_400(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables",
                             "queryStringParameters": {"offset": "-3"}})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Input robustness
# ---------------------------------------------------------------------------

def test_create_with_whitespace_only_name_returns_400(repo):
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables",
                             "body": json.dumps({"project_id": 10, "name": "   "})})
    assert resp["statusCode"] == 400
    assert "create_deliverable" not in repo.calls


def test_create_with_overlong_name_returns_400_not_500(repo):
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables",
                             "body": json.dumps({"project_id": 10, "name": "x" * 10000})})
    assert resp["statusCode"] == 400
    assert "create_deliverable" not in repo.calls


# ---------------------------------------------------------------------------
# Dependencies  (/deliverables/{id}/dependencies[/{depends_on_id}])
# ---------------------------------------------------------------------------

def test_get_dependencies_returns_200_with_both_sides(repo, monkeypatch):
    monkeypatch.setattr(function, "deliverable_exists", lambda i: True)
    monkeypatch.setattr(function, "get_dependencies", lambda i: [{"id": 2, "name": "B", "status": "in_progress"}])
    monkeypatch.setattr(function, "get_dependents", lambda i: [{"id": 9, "name": "Z", "status": "blocked"}])
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables/5/dependencies"})
    assert resp["statusCode"] == 200
    body = parse_body(resp)
    assert body["deliverable_id"] == 5
    assert body["depends_on"][0]["id"] == 2
    assert body["dependents"][0]["id"] == 9


def test_get_dependencies_unknown_deliverable_returns_404(repo, monkeypatch):
    monkeypatch.setattr(function, "deliverable_exists", lambda i: False)
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables/9999/dependencies"})
    assert resp["statusCode"] == 404


def test_add_dependency_returns_201(repo, monkeypatch):
    monkeypatch.setattr(function, "deliverable_exists", lambda i: True)
    monkeypatch.setattr(function, "path_exists", lambda a, b: False)
    seen = {}
    monkeypatch.setattr(function, "add_dependency", lambda d, o: (seen.update(d=d, o=o) or {"deliverable_id": d, "depends_on_id": o}))
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables/5/dependencies", "body": json.dumps({"depends_on_id": 2})})
    assert resp["statusCode"] == 201
    assert parse_body(resp) == {"deliverable_id": 5, "depends_on_id": 2}
    assert seen == {"d": 5, "o": 2}


def test_add_dependency_on_self_returns_400(repo, monkeypatch):
    monkeypatch.setattr(function, "deliverable_exists", lambda i: True)
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables/5/dependencies", "body": json.dumps({"depends_on_id": 5})})
    assert resp["statusCode"] == 400
    assert "itself" in parse_body(resp)["error"]


def test_add_dependency_missing_field_returns_400(repo, monkeypatch):
    monkeypatch.setattr(function, "deliverable_exists", lambda i: True)
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables/5/dependencies", "body": json.dumps({})})
    assert resp["statusCode"] == 400
    assert "depends_on_id" in parse_body(resp)["error"]


def test_add_dependency_missing_target_returns_400(repo, monkeypatch):
    monkeypatch.setattr(function, "deliverable_exists", lambda i: i == 5)  # base exists, target (2) does not
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables/5/dependencies", "body": json.dumps({"depends_on_id": 2})})
    assert resp["statusCode"] == 400
    assert "does not exist" in parse_body(resp)["error"]


def test_add_dependency_cycle_returns_400(repo, monkeypatch):
    monkeypatch.setattr(function, "deliverable_exists", lambda i: True)
    monkeypatch.setattr(function, "path_exists", lambda a, b: True)  # target already reaches base
    hit = {}
    monkeypatch.setattr(function, "add_dependency", lambda d, o: hit.update(called=True))
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables/5/dependencies", "body": json.dumps({"depends_on_id": 2})})
    assert resp["statusCode"] == 400
    assert "cycle" in parse_body(resp)["error"].lower()
    assert "called" not in hit  # never reached the insert


def test_add_dependency_duplicate_returns_400(repo, monkeypatch):
    monkeypatch.setattr(function, "deliverable_exists", lambda i: True)
    monkeypatch.setattr(function, "path_exists", lambda a, b: False)

    def _dup(d, o):
        raise DuplicateDependencyError((d, o))
    monkeypatch.setattr(function, "add_dependency", _dup)
    resp = function.handler({"httpMethod": "POST", "path": "/deliverables/5/dependencies", "body": json.dumps({"depends_on_id": 2})})
    assert resp["statusCode"] == 400
    assert "already depends" in parse_body(resp)["error"]


def test_remove_dependency_returns_204(repo, monkeypatch):
    monkeypatch.setattr(function, "remove_dependency", lambda d, o: {"deliverable_id": d, "depends_on_id": o})
    resp = function.handler({"httpMethod": "DELETE", "path": "/deliverables/5/dependencies/2"})
    assert resp["statusCode"] == 204
    assert resp["body"] == ""


def test_remove_dependency_missing_returns_404(repo, monkeypatch):
    monkeypatch.setattr(function, "remove_dependency", lambda d, o: None)
    resp = function.handler({"httpMethod": "DELETE", "path": "/deliverables/5/dependencies/2"})
    assert resp["statusCode"] == 404
