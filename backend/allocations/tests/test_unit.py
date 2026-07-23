"""
Unit tests — pure logic, no database.

Covers the allocations validation rules for create/update, including the
allocation-percentage bounds and the start/end date-order rule.
"""

import pytest

from validation import validate_create, validate_update

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# validate_create
# ---------------------------------------------------------------------------

def test_create_with_required_ids_only_is_valid():
    assert validate_create({"resource_id": 1, "project_id": 2}) == []


def test_create_with_all_fields_is_valid():
    errors = validate_create({
        "resource_id": 1,
        "project_id": 2,
        "allocation_pct": 50,
        "start_date": "2026-01-01",
        "end_date": "2026-06-30",
    })
    assert errors == []


def test_create_without_resource_id_reports_resource_id_error():
    errors = validate_create({"project_id": 2})
    assert any("resource_id" in e for e in errors)


def test_create_without_project_id_reports_project_id_error():
    errors = validate_create({"resource_id": 1})
    assert any("project_id" in e for e in errors)


def test_create_with_non_integer_ids_is_rejected():
    errors = validate_create({"resource_id": "a", "project_id": "b"})
    assert any("resource_id" in e for e in errors)
    assert any("project_id" in e for e in errors)


def test_create_with_bool_ids_is_rejected():
    errors = validate_create({"resource_id": True, "project_id": False})
    assert any("resource_id" in e for e in errors)
    assert any("project_id" in e for e in errors)


def test_create_with_non_dict_body_is_rejected():
    assert validate_create("nope") != []
    assert validate_create(None) != []


def test_create_with_allocation_pct_out_of_range_is_rejected():
    assert validate_create({"resource_id": 1, "project_id": 2, "allocation_pct": -1}) != []
    assert validate_create({"resource_id": 1, "project_id": 2, "allocation_pct": 101}) != []


def test_create_accepts_allocation_pct_boundaries():
    assert validate_create({"resource_id": 1, "project_id": 2, "allocation_pct": 0}) == []
    assert validate_create({"resource_id": 1, "project_id": 2, "allocation_pct": 100}) == []


def test_create_with_non_integer_allocation_pct_is_rejected():
    errors = validate_create({"resource_id": 1, "project_id": 2, "allocation_pct": "half"})
    assert any("allocation_pct" in e for e in errors)


def test_create_with_invalid_date_reports_date_error():
    errors = validate_create({"resource_id": 1, "project_id": 2, "start_date": "01-01-2026"})
    assert any("start_date" in e for e in errors)


# --- date-order rule -------------------------------------------------------

def test_create_with_end_before_start_is_rejected():
    errors = validate_create({
        "resource_id": 1, "project_id": 2,
        "start_date": "2026-06-30", "end_date": "2026-01-01",
    })
    assert any("end_date" in e and "before" in e for e in errors)


def test_create_with_end_equal_start_is_valid():
    errors = validate_create({
        "resource_id": 1, "project_id": 2,
        "start_date": "2026-01-01", "end_date": "2026-01-01",
    })
    assert errors == []


def test_create_with_end_after_start_is_valid():
    errors = validate_create({
        "resource_id": 1, "project_id": 2,
        "start_date": "2026-01-01", "end_date": "2026-12-31",
    })
    assert errors == []


def test_create_with_only_one_date_is_valid():
    assert validate_create({"resource_id": 1, "project_id": 2, "start_date": "2026-01-01"}) == []
    assert validate_create({"resource_id": 1, "project_id": 2, "end_date": "2026-01-01"}) == []


# ---------------------------------------------------------------------------
# validate_update
# ---------------------------------------------------------------------------

def test_update_with_partial_fields_is_valid():
    assert validate_update({"allocation_pct": 75}) == []


def test_update_with_empty_body_is_valid():
    assert validate_update({}) == []


def test_update_with_non_integer_ids_is_rejected():
    errors = validate_update({"resource_id": "x", "project_id": "y"})
    assert any("resource_id" in e for e in errors)
    assert any("project_id" in e for e in errors)


def test_update_with_allocation_pct_out_of_range_is_rejected():
    assert validate_update({"allocation_pct": 200}) != []


def test_update_enforces_date_order():
    errors = validate_update({"start_date": "2026-06-01", "end_date": "2026-05-01"})
    assert any("end_date" in e for e in errors)
