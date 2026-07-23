"""
Unit tests — pure logic, no database, no handler.

Exercises the auth validation rules (register / login / user-update) by importing
the validators directly. Uniqueness of username/email is a DB concern and is
covered by the integration suite, not here.
"""

import pytest

from validation import validate_register, validate_login, validate_user_update

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# validate_register
# ---------------------------------------------------------------------------

def test_register_with_all_valid_fields_passes():
    assert validate_register({
        "username": "ada", "email": "ada@example.com", "password": "password123",
    }) == []


def test_register_with_a_valid_role_passes():
    assert validate_register({
        "username": "ada", "email": "ada@example.com", "password": "password123",
        "role": "Manager",
    }) == []


def test_register_with_non_dict_body_is_rejected():
    assert validate_register("not a dict") != []
    assert validate_register(None) != []


def test_register_with_missing_username_is_rejected():
    errors = validate_register({"email": "ada@example.com", "password": "password123"})
    assert any("username" in e for e in errors)


def test_register_with_blank_username_is_rejected():
    errors = validate_register({"username": "   ", "email": "ada@example.com", "password": "password123"})
    assert any("username" in e for e in errors)


def test_register_with_missing_email_is_rejected():
    errors = validate_register({"username": "ada", "password": "password123"})
    assert any("email" in e for e in errors)


def test_register_with_invalid_email_is_rejected():
    errors = validate_register({"username": "ada", "email": "not-an-email", "password": "password123"})
    assert any("email" in e for e in errors)


def test_register_with_too_short_password_is_rejected():
    errors = validate_register({"username": "ada", "email": "ada@example.com", "password": "short"})
    assert any("password" in e for e in errors)


def test_register_with_too_long_password_is_rejected():
    errors = validate_register({"username": "ada", "email": "ada@example.com", "password": "x" * 73})
    assert any("password" in e for e in errors)


def test_register_with_blank_role_is_rejected():
    errors = validate_register({
        "username": "ada", "email": "ada@example.com", "password": "password123", "role": "   ",
    })
    assert any("role" in e for e in errors)


def test_register_reports_all_errors_at_once():
    errors = validate_register({"email": "bad", "password": "x"})
    assert len(errors) >= 3  # missing username + invalid email + short password


# ---------------------------------------------------------------------------
# validate_login
# ---------------------------------------------------------------------------

def test_login_with_username_and_password_passes():
    assert validate_login({"username": "ada", "password": "password123"}) == []


def test_login_with_email_identifier_passes():
    assert validate_login({"email": "ada@example.com", "password": "password123"}) == []


def test_login_without_identifier_is_rejected():
    assert validate_login({"password": "password123"}) != []


def test_login_without_password_is_rejected():
    assert validate_login({"username": "ada"}) != []


# ---------------------------------------------------------------------------
# validate_user_update (partial update — fields optional but well-formed)
# ---------------------------------------------------------------------------

def test_user_update_with_partial_fields_is_valid():
    assert validate_user_update({"username": "sam2"}) == []


def test_user_update_with_empty_body_is_valid():
    assert validate_user_update({}) == []  # nothing to change is a valid no-op


def test_user_update_with_blank_username_is_rejected():
    assert validate_user_update({"username": "   "}) != []


def test_user_update_with_invalid_email_is_rejected():
    errors = validate_user_update({"email": "not-an-email"})
    assert any("email" in e for e in errors)
