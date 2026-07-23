"""
Unit tests — pure logic, no database.

Covers the projects validation rules, the shared ?search= parser, and the shared
activity helpers (diff / actor / record-never-raises). The activity module is
synced identically into every service, so its pure logic is exercised once here.
"""

from datetime import date
from decimal import Decimal

import pytest

import activity
import auth
from validation import validate_create, validate_update, VALID_STATUSES
from pagination import parse_search, PaginationError, MAX_SEARCH_LEN

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# validate_create
# ---------------------------------------------------------------------------

def test_create_with_only_name_is_valid():
    assert validate_create({"name": "Apollo"}) == []


def test_create_with_all_fields_is_valid():
    errors = validate_create({
        "name": "Apollo",
        "description": "Moon program",
        "status": "active",
        "department": "R&D",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "deadline": "2026-11-30",
        "budget_planned": 1000000,
        "budget_consumed": "250000.50",
    })
    assert errors == []


def test_create_without_name_reports_name_error():
    errors = validate_create({"description": "no name"})
    assert any("name" in e for e in errors)


def test_create_with_blank_name_is_rejected():
    assert validate_create({"name": ""}) != []
    assert validate_create({"name": "   "}) != []


def test_create_with_non_dict_body_is_rejected():
    assert validate_create("not a dict") != []
    assert validate_create(None) != []


def test_create_with_invalid_status_reports_status_error():
    errors = validate_create({"name": "X", "status": "archived"})
    assert any("status" in e for e in errors)


def test_create_accepts_every_valid_status():
    for status in VALID_STATUSES:
        assert validate_create({"name": "X", "status": status}) == []


def test_create_with_non_numeric_budget_is_rejected():
    errors = validate_create({"name": "X", "budget_planned": "lots"})
    assert any("budget_planned" in e for e in errors)


def test_create_with_bool_budget_is_rejected():
    # Bools are ints in Python; they must not pass as valid numbers.
    errors = validate_create({"name": "X", "budget_consumed": True})
    assert any("budget_consumed" in e for e in errors)


def test_create_with_invalid_date_reports_date_error():
    errors = validate_create({"name": "X", "start_date": "31-12-2026"})
    assert any("start_date" in e for e in errors)


def test_create_reports_all_errors_at_once():
    errors = validate_create({"status": "nope", "budget_planned": "x"})
    assert len(errors) >= 3  # missing name + bad status + bad budget


# ---------------------------------------------------------------------------
# validate_update
# ---------------------------------------------------------------------------

def test_update_with_partial_fields_is_valid():
    assert validate_update({"status": "completed"}) == []


def test_update_with_empty_body_is_valid():
    assert validate_update({}) == []  # nothing to change is a valid no-op


def test_update_without_name_is_valid():
    assert validate_update({"department": "Ops"}) == []


def test_update_with_blank_name_is_rejected():
    assert validate_update({"name": ""}) != []
    assert validate_update({"name": None}) != []


def test_update_with_invalid_status_is_rejected():
    errors = validate_update({"status": "archived"})
    assert any("status" in e for e in errors)


def test_update_with_invalid_date_and_budget_reports_both():
    errors = validate_update({"end_date": "not-a-date", "budget_consumed": "x"})
    assert any("end_date" in e for e in errors)
    assert any("budget_consumed" in e for e in errors)


# ---------------------------------------------------------------------------
# parse_search (shared ?search= validator)
# ---------------------------------------------------------------------------

def test_parse_search_absent_or_blank_returns_none():
    assert parse_search({}) is None
    assert parse_search({"search": ""}) is None
    assert parse_search({"search": "   "}) is None


def test_parse_search_trims_whitespace():
    assert parse_search({"search": "  apollo  "}) == "apollo"


def test_parse_search_passes_through_a_normal_term():
    assert parse_search({"search": "Data Warehouse"}) == "Data Warehouse"


def test_parse_search_rejects_overlong_term():
    with pytest.raises(PaginationError):
        parse_search({"search": "x" * (MAX_SEARCH_LEN + 1)})


def test_parse_search_accepts_max_length_term():
    term = "x" * MAX_SEARCH_LEN
    assert parse_search({"search": term}) == term


def test_parse_search_rejects_non_string():
    with pytest.raises(PaginationError):
        parse_search({"search": ["a", "b"]})


def test_parse_search_supports_a_custom_key():
    assert parse_search({"q": "hi"}, key="q") == "hi"


# ---------------------------------------------------------------------------
# activity.diff — field-level change detection
# ---------------------------------------------------------------------------

def test_diff_reports_field_level_changes():
    before = {"id": 1, "name": "Apollo", "status": "planning", "budget_planned": Decimal("100.00")}
    after = {"id": 1, "name": "Apollo", "status": "active", "budget_planned": Decimal("100.00")}
    assert activity.diff(before, after) == [{"field": "status", "old": "planning", "new": "active"}]


def test_diff_ignores_id_and_timestamps():
    before = {"id": 1, "created_at": "a", "updated_at": "b", "name": "X"}
    after = {"id": 1, "created_at": "c", "updated_at": "d", "name": "Y"}
    assert [c["field"] for c in activity.diff(before, after)] == ["name"]


def test_diff_coerces_decimal_and_dates_to_json_safe():
    before = {"budget_planned": Decimal("1.50"), "deadline": date(2026, 1, 1)}
    after = {"budget_planned": Decimal("2.50"), "deadline": date(2026, 2, 2)}
    changes = {c["field"]: (c["old"], c["new"]) for c in activity.diff(before, after)}
    assert changes["budget_planned"] == (1.5, 2.5)              # Decimal -> float
    assert changes["deadline"] == ("2026-01-01", "2026-02-02")  # date -> ISO string


def test_diff_is_empty_when_nothing_changed():
    row = {"id": 1, "name": "Apollo", "status": "active"}
    assert activity.diff(row, dict(row)) == []


# ---------------------------------------------------------------------------
# activity.actor — best-effort actor extraction from the bearer token
# ---------------------------------------------------------------------------

def test_actor_extracts_id_and_username_from_bearer_token():
    token = auth.create_token({"sub": "42", "username": "lalitha", "role": "Admin"})
    assert activity.actor({"headers": {"Authorization": f"Bearer {token}"}}) == {"id": 42, "username": "lalitha"}


def test_actor_is_anonymous_without_a_token():
    assert activity.actor({"headers": {}}) == {"id": None, "username": None}
    assert activity.actor({}) == {"id": None, "username": None}


def test_actor_is_anonymous_on_a_garbage_token():
    assert activity.actor({"headers": {"Authorization": "Bearer not-a-jwt"}}) == {"id": None, "username": None}


# ---------------------------------------------------------------------------
# activity.record — must NEVER raise (logging can't break the main operation)
# ---------------------------------------------------------------------------

def test_record_swallows_db_errors_and_returns_none(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db is on fire")
    monkeypatch.setattr("postgres_service.execute", boom)
    assert activity.record({"id": 1, "username": "x"}, "created", "project", 1, "X") is None


def test_record_falls_back_to_null_actor_without_raising(monkeypatch):
    captured = {}
    monkeypatch.setattr("postgres_service.execute", lambda sql, params, **k: captured.update(params=params))
    activity.record(None, "created", "project", 1, "X")
    assert captured["params"][0] is None and captured["params"][1] is None
