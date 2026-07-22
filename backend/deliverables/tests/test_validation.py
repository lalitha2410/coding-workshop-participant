"""Unit tests for validation.py (pure functions, no database)."""

from validation import validate_create, validate_update, VALID_STATUSES


# ---------------------------------------------------------------------------
# validate_create
# ---------------------------------------------------------------------------

def test_create_minimal_valid():
    assert validate_create({"project_id": 1, "name": "Design doc"}) == []


def test_create_full_valid():
    errors = validate_create({
        "project_id": 1,
        "name": "Design doc",
        "description": "Architecture write-up",
        "status": "in_progress",
        "completion_pct": 40,
        "due_date": "2026-06-30",
    })
    assert errors == []


def test_create_missing_project_id():
    errors = validate_create({"name": "Design doc"})
    assert any("project_id" in e for e in errors)


def test_create_non_integer_project_id():
    errors = validate_create({"project_id": "abc", "name": "Design doc"})
    assert any("project_id" in e for e in errors)


def test_create_bool_project_id_rejected():
    errors = validate_create({"project_id": True, "name": "Design doc"})
    assert any("project_id" in e for e in errors)


def test_create_missing_name():
    errors = validate_create({"project_id": 1})
    assert any("name" in e for e in errors)


def test_create_empty_name():
    assert validate_create({"project_id": 1, "name": ""}) != []
    assert validate_create({"project_id": 1, "name": "   "}) != []


def test_create_non_dict_body():
    assert validate_create("not a dict") != []
    assert validate_create(None) != []


def test_create_invalid_status():
    errors = validate_create({"project_id": 1, "name": "X", "status": "done"})
    assert any("status" in e for e in errors)


def test_create_all_valid_statuses_accepted():
    for status in VALID_STATUSES:
        assert validate_create({"project_id": 1, "name": "X", "status": status}) == []


def test_create_completion_pct_out_of_range():
    assert validate_create({"project_id": 1, "name": "X", "completion_pct": -1}) != []
    assert validate_create({"project_id": 1, "name": "X", "completion_pct": 101}) != []


def test_create_completion_pct_boundaries_valid():
    assert validate_create({"project_id": 1, "name": "X", "completion_pct": 0}) == []
    assert validate_create({"project_id": 1, "name": "X", "completion_pct": 100}) == []


def test_create_completion_pct_non_integer():
    errors = validate_create({"project_id": 1, "name": "X", "completion_pct": "half"})
    assert any("completion_pct" in e for e in errors)


def test_create_completion_pct_bool_rejected():
    errors = validate_create({"project_id": 1, "name": "X", "completion_pct": True})
    assert any("completion_pct" in e for e in errors)


def test_create_invalid_date():
    errors = validate_create({"project_id": 1, "name": "X", "due_date": "30-06-2026"})
    assert any("due_date" in e for e in errors)


def test_create_reports_multiple_errors():
    errors = validate_create({"status": "nope", "completion_pct": 500})
    # missing project_id + missing name + bad status + bad pct
    assert len(errors) >= 4


# ---------------------------------------------------------------------------
# validate_update
# ---------------------------------------------------------------------------

def test_update_partial_valid():
    assert validate_update({"status": "completed"}) == []


def test_update_empty_body_valid():
    assert validate_update({}) == []


def test_update_fields_absent_is_ok():
    assert validate_update({"completion_pct": 75}) == []


def test_update_empty_name_rejected():
    assert validate_update({"name": ""}) != []
    assert validate_update({"name": None}) != []


def test_update_non_integer_project_id_rejected():
    errors = validate_update({"project_id": "abc"})
    assert any("project_id" in e for e in errors)


def test_update_invalid_status():
    errors = validate_update({"status": "done"})
    assert any("status" in e for e in errors)


def test_update_completion_pct_range_and_date():
    errors = validate_update({"completion_pct": 200, "due_date": "not-a-date"})
    assert any("completion_pct" in e for e in errors)
    assert any("due_date" in e for e in errors)
