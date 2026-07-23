"""
Unit tests — pure logic, no database.

Covers the resources validation rules (validate_create / validate_update).
"""

import pytest

from validation import validate_create, validate_update

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# validate_create
# ---------------------------------------------------------------------------

def test_create_with_name_and_email_is_valid():
    assert validate_create({"name": "Ada Lovelace", "email": "ada@example.com"}) == []


def test_create_with_all_fields_is_valid():
    errors = validate_create({
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "title": "Principal Engineer",
    })
    assert errors == []


def test_create_without_name_reports_name_error():
    errors = validate_create({"email": "ada@example.com"})
    assert any("name" in e for e in errors)


def test_create_with_blank_name_is_rejected():
    assert validate_create({"name": "", "email": "ada@example.com"}) != []
    assert validate_create({"name": "   ", "email": "ada@example.com"}) != []


def test_create_without_email_reports_email_error():
    errors = validate_create({"name": "Ada"})
    assert any("email" in e for e in errors)


def test_create_with_empty_email_reports_email_error():
    errors = validate_create({"name": "Ada", "email": ""})
    assert any("email" in e for e in errors)


def test_create_with_non_dict_body_is_rejected():
    assert validate_create("not a dict") != []
    assert validate_create(None) != []


def test_create_rejects_malformed_email_formats():
    for bad in ("plainaddress", "no-at-sign.com", "a@b", "a@@b.com", "a b@c.com", "a@b .com"):
        errors = validate_create({"name": "Ada", "email": bad})
        assert any("email" in e for e in errors), f"expected email error for {bad!r}"


def test_create_accepts_well_formed_email_formats():
    for good in ("ada@example.com", "a.b+tag@sub.domain.co", "user_name@host.io"):
        assert validate_create({"name": "Ada", "email": good}) == [], f"expected {good!r} valid"


def test_create_missing_email_reports_required_not_format():
    # A missing email should read as "required", not "invalid format".
    errors = validate_create({"name": "Ada"})
    assert any("required" in e for e in errors)


def test_create_reports_multiple_errors_at_once():
    errors = validate_create({"email": "bad"})
    # missing name + invalid email
    assert len(errors) >= 2


# ---------------------------------------------------------------------------
# validate_update
# ---------------------------------------------------------------------------

def test_update_with_partial_fields_is_valid():
    assert validate_update({"title": "Staff Engineer"}) == []


def test_update_with_empty_body_is_valid():
    assert validate_update({}) == []


def test_update_with_email_only_is_valid():
    assert validate_update({"email": "new@example.com"}) == []


def test_update_with_blank_name_is_rejected():
    assert validate_update({"name": ""}) != []


def test_update_with_invalid_email_is_rejected():
    errors = validate_update({"email": "not-an-email"})
    assert any("email" in e for e in errors)


def test_update_with_empty_email_is_rejected():
    # Present but empty is invalid (can't clear a NOT NULL / required field).
    errors = validate_update({"email": ""})
    assert any("email" in e for e in errors)


def test_update_without_email_is_valid():
    assert validate_update({"name": "Ada"}) == []
