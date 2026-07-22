"""Unit tests for validation.py (pure functions, no database)."""

from validation import validate_create, validate_update, VALID_STATUSES


# ---------------------------------------------------------------------------
# validate_create
# ---------------------------------------------------------------------------

def test_create_minimal_valid():
    assert validate_create({"name": "Apollo"}) == []


def test_create_full_valid():
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


def test_create_missing_name():
    errors = validate_create({"description": "no name"})
    assert any("name" in e for e in errors)


def test_create_empty_name():
    assert validate_create({"name": ""}) != []
    assert validate_create({"name": "   "}) != []


def test_create_non_dict_body():
    assert validate_create("not a dict") != []
    assert validate_create(None) != []


def test_create_invalid_status():
    errors = validate_create({"name": "X", "status": "archived"})
    assert any("status" in e for e in errors)


def test_create_all_valid_statuses_accepted():
    for status in VALID_STATUSES:
        assert validate_create({"name": "X", "status": status}) == []


def test_create_non_numeric_budget():
    errors = validate_create({"name": "X", "budget_planned": "lots"})
    assert any("budget_planned" in e for e in errors)


def test_create_bool_budget_rejected():
    # Bools are ints in Python; they must not pass as valid numbers.
    errors = validate_create({"name": "X", "budget_consumed": True})
    assert any("budget_consumed" in e for e in errors)


def test_create_invalid_date():
    errors = validate_create({"name": "X", "start_date": "31-12-2026"})
    assert any("start_date" in e for e in errors)


def test_create_reports_multiple_errors():
    errors = validate_create({"status": "nope", "budget_planned": "x"})
    # missing name + bad status + bad budget
    assert len(errors) >= 3


# ---------------------------------------------------------------------------
# validate_update
# ---------------------------------------------------------------------------

def test_update_partial_valid():
    assert validate_update({"status": "completed"}) == []


def test_update_empty_body_valid():
    # Nothing to change is still a valid (no-op) update payload.
    assert validate_update({}) == []


def test_update_name_absent_is_ok():
    assert validate_update({"department": "Ops"}) == []


def test_update_empty_name_rejected():
    assert validate_update({"name": ""}) != []
    assert validate_update({"name": None}) != []


def test_update_invalid_status():
    errors = validate_update({"status": "archived"})
    assert any("status" in e for e in errors)


def test_update_invalid_date_and_budget():
    errors = validate_update({"end_date": "not-a-date", "budget_consumed": "x"})
    assert any("end_date" in e for e in errors)
    assert any("budget_consumed" in e for e in errors)
