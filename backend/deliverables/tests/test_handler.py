"""
Unit tests for the function.handler router (deliverables service).

The repository layer — including the project_exists reference check — is
monkeypatched, so these tests exercise routing, status codes, request parsing,
and response shaping without touching a database.
"""

import json
from datetime import date

import pytest

import function


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _body(response):
    """Parse the JSON body of a handler response (empty string -> None)."""
    raw = response["body"]
    return json.loads(raw) if raw else None


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

    # Default: referenced project exists, so create/update reach the DB layer.
    monkeypatch.setattr(function, "project_exists", lambda pid: True)
    return Repo()


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------

def test_list_returns_200_and_passes_filters(repo):
    repo.set("list_deliverables", [SAMPLE_DELIVERABLE])
    event = {
        "httpMethod": "GET",
        "path": "/deliverables",
        "queryStringParameters": {"project_id": "10", "status": "in_progress"},
    }
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert _body(resp)[0]["name"] == "Design doc"
    assert repo.calls["list_deliverables"]["kwargs"] == {"project_id": "10", "status": "in_progress"}


def test_get_one_found_returns_200(repo):
    repo.set("get_deliverable", SAMPLE_DELIVERABLE)
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables/1"})
    assert resp["statusCode"] == 200
    assert repo.calls["get_deliverable"]["args"] == (1,)


def test_get_one_not_found_returns_404(repo):
    repo.set("get_deliverable", None)
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables/999"})
    assert resp["statusCode"] == 404


def test_get_one_non_numeric_id_returns_404(repo):
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
    assert _body(resp)["name"] == "Design doc"


def test_create_invalid_returns_400(repo):
    # Missing project_id and name -> validation fails before the DB is touched.
    event = {"httpMethod": "POST", "path": "/deliverables", "body": json.dumps({"description": "x"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "details" in _body(resp)


def test_create_missing_project_returns_400(repo, monkeypatch):
    # Payload is valid, but the referenced project does not exist.
    monkeypatch.setattr(function, "project_exists", lambda pid: False)
    repo.set("create_deliverable", SAMPLE_DELIVERABLE)  # should never be called
    event = {"httpMethod": "POST", "path": "/deliverables",
             "body": json.dumps({"project_id": 9999, "name": "Orphan"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "does not exist" in _body(resp)["error"]
    assert "create_deliverable" not in repo.calls


def test_create_malformed_json_returns_400():
    event = {"httpMethod": "POST", "path": "/deliverables", "body": "{not json"}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# PUT
# ---------------------------------------------------------------------------

def test_update_valid_returns_200(repo):
    repo.set("update_deliverable", SAMPLE_DELIVERABLE)
    event = {"httpMethod": "PUT", "path": "/deliverables/1",
             "body": json.dumps({"status": "completed"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert repo.calls["update_deliverable"]["args"][0] == 1


def test_update_not_found_returns_404(repo):
    repo.set("update_deliverable", None)
    event = {"httpMethod": "PUT", "path": "/deliverables/999",
             "body": json.dumps({"status": "completed"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 404


def test_update_missing_project_returns_400(repo, monkeypatch):
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


def test_update_invalid_payload_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/deliverables/1",
             "body": json.dumps({"completion_pct": 500})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def test_delete_found_returns_204_with_empty_body(repo):
    repo.set("delete_deliverable", {"id": 1})
    resp = function.handler({"httpMethod": "DELETE", "path": "/deliverables/1"})
    assert resp["statusCode"] == 204
    assert resp["body"] == ""


def test_delete_not_found_returns_404(repo):
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


def test_api_gateway_v2_event_shape(repo):
    repo.set("list_deliverables", [])
    event = {"requestContext": {"http": {"method": "GET"}}, "rawPath": "/deliverables"}
    resp = function.handler(event)
    assert resp["statusCode"] == 200


def test_response_serializes_dates(repo):
    repo.set("get_deliverable", SAMPLE_DELIVERABLE)
    resp = function.handler({"httpMethod": "GET", "path": "/deliverables/1"})
    body = _body(resp)
    assert body["due_date"] == "2026-06-30"  # date -> ISO string
