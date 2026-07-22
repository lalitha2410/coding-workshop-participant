"""Unit tests for validation.py (pure functions, no database)."""

from validation import validate_create, validate_update


# ---------------------------------------------------------------------------
# validate_create
# ---------------------------------------------------------------------------

def test_create_minimal_valid():
    assert validate_create({"name": "Ada Lovelace", "email": "ada@example.com"}) == []


def test_create_full_valid():
    errors = validate_create({
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "title": "Principal Engineer",
    })
    assert errors == []


def test_create_missing_name():
    errors = validate_create({"email": "ada@example.com"})
    assert any("name" in e for e in errors)


def test_create_empty_name():
    assert validate_create({"name": "", "email": "ada@example.com"}) != []
    assert validate_create({"name": "   ", "email": "ada@example.com"}) != []


def test_create_missing_email():
    errors = validate_create({"name": "Ada"})
    assert any("email" in e for e in errors)


def test_create_empty_email():
    errors = validate_create({"name": "Ada", "email": ""})
    assert any("email" in e for e in errors)


def test_create_non_dict_body():
    assert validate_create("not a dict") != []
    assert validate_create(None) != []


def test_create_invalid_email_formats():
    for bad in ("plainaddress", "no-at-sign.com", "a@b", "a@@b.com", "a b@c.com", "a@b .com"):
        errors = validate_create({"name": "Ada", "email": bad})
        assert any("email" in e for e in errors), f"expected email error for {bad!r}"


def test_create_valid_email_formats():
    for good in ("ada@example.com", "a.b+tag@sub.domain.co", "user_name@host.io"):
        assert validate_create({"name": "Ada", "email": good}) == [], f"expected {good!r} valid"


def test_create_missing_email_reports_required_not_format():
    # A missing email should read as "required", not "invalid format".
    errors = validate_create({"name": "Ada"})
    assert any("required" in e for e in errors)


def test_create_reports_multiple_errors():
    errors = validate_create({"email": "bad"})
    # missing name + invalid email
    assert len(errors) >= 2


# ---------------------------------------------------------------------------
# validate_update
# ---------------------------------------------------------------------------

def test_update_partial_valid():
    assert validate_update({"title": "Staff Engineer"}) == []


def test_update_empty_body_valid():
    assert validate_update({}) == []


def test_update_email_only_valid():
    assert validate_update({"email": "new@example.com"}) == []


def test_update_empty_name_rejected():
    assert validate_update({"name": ""}) != []


def test_update_invalid_email_rejected():
    errors = validate_update({"email": "not-an-email"})
    assert any("email" in e for e in errors)


def test_update_empty_email_rejected():
    # Present but empty is invalid (can't clear a NOT NULL / required field).
    errors = validate_update({"email": ""})
    assert any("email" in e for e in errors)


def test_update_email_absent_is_ok():
    assert validate_update({"name": "Ada"}) == []
