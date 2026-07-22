"""Unit tests for validation.py (pure functions, no database)."""

from validation import validate_create, validate_update


# ---------------------------------------------------------------------------
# validate_create
# ---------------------------------------------------------------------------

def test_create_minimal_valid():
    assert validate_create({"resource_id": 1, "project_id": 2}) == []


def test_create_full_valid():
    errors = validate_create({
        "resource_id": 1,
        "project_id": 2,
        "allocation_pct": 50,
        "start_date": "2026-01-01",
        "end_date": "2026-06-30",
    })
    assert errors == []


def test_create_missing_resource_id():
    errors = validate_create({"project_id": 2})
    assert any("resource_id" in e for e in errors)


def test_create_missing_project_id():
    errors = validate_create({"resource_id": 1})
    assert any("project_id" in e for e in errors)


def test_create_non_integer_ids():
    errors = validate_create({"resource_id": "a", "project_id": "b"})
    assert any("resource_id" in e for e in errors)
    assert any("project_id" in e for e in errors)


def test_create_bool_ids_rejected():
    errors = validate_create({"resource_id": True, "project_id": False})
    assert any("resource_id" in e for e in errors)
    assert any("project_id" in e for e in errors)


def test_create_non_dict_body():
    assert validate_create("nope") != []
    assert validate_create(None) != []


def test_create_allocation_pct_out_of_range():
    assert validate_create({"resource_id": 1, "project_id": 2, "allocation_pct": -1}) != []
    assert validate_create({"resource_id": 1, "project_id": 2, "allocation_pct": 101}) != []


def test_create_allocation_pct_boundaries_valid():
    assert validate_create({"resource_id": 1, "project_id": 2, "allocation_pct": 0}) == []
    assert validate_create({"resource_id": 1, "project_id": 2, "allocation_pct": 100}) == []


def test_create_allocation_pct_non_integer():
    errors = validate_create({"resource_id": 1, "project_id": 2, "allocation_pct": "half"})
    assert any("allocation_pct" in e for e in errors)


def test_create_invalid_dates():
    errors = validate_create({"resource_id": 1, "project_id": 2, "start_date": "01-01-2026"})
    assert any("start_date" in e for e in errors)


# --- date-order rule -------------------------------------------------------

def test_end_before_start_rejected():
    errors = validate_create({
        "resource_id": 1, "project_id": 2,
        "start_date": "2026-06-30", "end_date": "2026-01-01",
    })
    assert any("end_date" in e and "before" in e for e in errors)


def test_end_equal_start_valid():
    errors = validate_create({
        "resource_id": 1, "project_id": 2,
        "start_date": "2026-01-01", "end_date": "2026-01-01",
    })
    assert errors == []


def test_end_after_start_valid():
    errors = validate_create({
        "resource_id": 1, "project_id": 2,
        "start_date": "2026-01-01", "end_date": "2026-12-31",
    })
    assert errors == []


def test_only_one_date_is_fine():
    assert validate_create({"resource_id": 1, "project_id": 2, "start_date": "2026-01-01"}) == []
    assert validate_create({"resource_id": 1, "project_id": 2, "end_date": "2026-01-01"}) == []


# ---------------------------------------------------------------------------
# validate_update
# ---------------------------------------------------------------------------

def test_update_partial_valid():
    assert validate_update({"allocation_pct": 75}) == []


def test_update_empty_body_valid():
    assert validate_update({}) == []


def test_update_non_integer_ids_rejected():
    errors = validate_update({"resource_id": "x", "project_id": "y"})
    assert any("resource_id" in e for e in errors)
    assert any("project_id" in e for e in errors)


def test_update_allocation_pct_range():
    assert validate_update({"allocation_pct": 200}) != []


def test_update_date_order_enforced():
    errors = validate_update({"start_date": "2026-06-01", "end_date": "2026-05-01"})
    assert any("end_date" in e for e in errors)
