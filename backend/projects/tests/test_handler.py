"""
Unit tests for the function.handler router.

The repository layer is monkeypatched, so these tests exercise routing, status
codes, request parsing, and response shaping without touching a database.
"""

import json
from datetime import date
from decimal import Decimal

import pytest

import function


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _body(response):
    """Parse the JSON body of a handler response (empty string -> None)."""
    raw = response["body"]
    return json.loads(raw) if raw else None


SAMPLE_PROJECT = {
    "id": 1,
    "name": "Apollo",
    "description": "Moon program",
    "status": "active",
    "department": "R&D",
    "start_date": date(2026, 1, 1),
    "end_date": date(2026, 12, 31),
    "deadline": date(2026, 11, 30),
    "budget_planned": Decimal("1000000.00"),
    "budget_consumed": Decimal("250000.50"),
}


@pytest.fixture
def repo(monkeypatch):
    """Replace every repository call on the function module with a stub recorder."""
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

def test_list_returns_200_and_passes_filters(repo):
    repo.set("list_projects", [SAMPLE_PROJECT])
    event = {
        "httpMethod": "GET",
        "path": "/projects",
        "queryStringParameters": {"status": "active", "department": "R&D"},
    }
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert _body(resp)[0]["name"] == "Apollo"
    assert repo.calls["list_projects"]["kwargs"] == {"status": "active", "department": "R&D"}


def test_get_one_found_returns_200(repo):
    repo.set("get_project", SAMPLE_PROJECT)
    resp = function.handler({"httpMethod": "GET", "path": "/projects/1"})
    assert resp["statusCode"] == 200
    assert repo.calls["get_project"]["args"] == (1,)


def test_get_one_not_found_returns_404(repo):
    repo.set("get_project", None)
    resp = function.handler({"httpMethod": "GET", "path": "/projects/999"})
    assert resp["statusCode"] == 404


def test_get_one_non_numeric_id_returns_404(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/projects/abc"})
    assert resp["statusCode"] == 404


def test_get_uses_path_parameters_when_present(repo):
    repo.set("get_project", SAMPLE_PROJECT)
    event = {"httpMethod": "GET", "pathParameters": {"id": "1"}}
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert repo.calls["get_project"]["args"] == (1,)


# ---------------------------------------------------------------------------
# POST
# ---------------------------------------------------------------------------

def test_create_valid_returns_201(repo):
    repo.set("create_project", SAMPLE_PROJECT)
    event = {"httpMethod": "POST", "path": "/projects", "body": json.dumps({"name": "Apollo"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 201
    assert _body(resp)["name"] == "Apollo"


def test_create_invalid_returns_400(repo):
    # No repo stub needed: validation should fail before the DB is touched.
    event = {"httpMethod": "POST", "path": "/projects", "body": json.dumps({"description": "no name"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "details" in _body(resp)


def test_create_malformed_json_returns_400():
    event = {"httpMethod": "POST", "path": "/projects", "body": "{not json"}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


def test_create_accepts_dict_body(repo):
    # Some local invokers pass an already-parsed dict rather than a JSON string.
    repo.set("create_project", SAMPLE_PROJECT)
    event = {"httpMethod": "POST", "path": "/projects", "body": {"name": "Apollo"}}
    resp = function.handler(event)
    assert resp["statusCode"] == 201


# ---------------------------------------------------------------------------
# PUT
# ---------------------------------------------------------------------------

def test_update_valid_returns_200(repo):
    repo.set("update_project", SAMPLE_PROJECT)
    event = {"httpMethod": "PUT", "path": "/projects/1", "body": json.dumps({"status": "completed"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert repo.calls["update_project"]["args"][0] == 1


def test_update_not_found_returns_404(repo):
    repo.set("update_project", None)
    event = {"httpMethod": "PUT", "path": "/projects/999", "body": json.dumps({"status": "completed"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 404


def test_update_without_id_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/projects", "body": json.dumps({"status": "completed"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


def test_update_invalid_payload_returns_400(repo):
    event = {"httpMethod": "PUT", "path": "/projects/1", "body": json.dumps({"status": "archived"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def test_delete_found_returns_204_with_empty_body(repo):
    repo.set("delete_project", {"id": 1})
    resp = function.handler({"httpMethod": "DELETE", "path": "/projects/1"})
    assert resp["statusCode"] == 204
    assert resp["body"] == ""


def test_delete_not_found_returns_404(repo):
    repo.set("delete_project", None)
    resp = function.handler({"httpMethod": "DELETE", "path": "/projects/999"})
    assert resp["statusCode"] == 404


def test_delete_without_id_returns_400(repo):
    resp = function.handler({"httpMethod": "DELETE", "path": "/projects"})
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------

def test_unsupported_method_returns_400(repo):
    resp = function.handler({"httpMethod": "PATCH", "path": "/projects/1"})
    assert resp["statusCode"] == 400


def test_repository_error_returns_500(repo):
    repo.set("list_projects", RuntimeError("db down"))
    resp = function.handler({"httpMethod": "GET", "path": "/projects"})
    assert resp["statusCode"] == 500


def test_api_gateway_v2_event_shape(repo):
    repo.set("list_projects", [])
    event = {"requestContext": {"http": {"method": "GET"}}, "rawPath": "/projects"}
    resp = function.handler(event)
    assert resp["statusCode"] == 200


def test_response_serializes_dates_and_decimals(repo):
    repo.set("get_project", SAMPLE_PROJECT)
    resp = function.handler({"httpMethod": "GET", "path": "/projects/1"})
    body = _body(resp)
    assert body["start_date"] == "2026-01-01"          # date -> ISO string
    assert body["budget_planned"] == 1000000.0         # Decimal -> float
