"""
Validation for auth request payloads (register / login).

Each validator returns a list of human-readable error strings (empty list when
the payload is valid), so the handler can turn any non-empty result into a 400.
These checks are pure (no database). Uniqueness of username/email is enforced at
the DB layer and surfaced as a 400 by the handler.
"""

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# bcrypt only uses the first 72 bytes; cap here so nothing is silently ignored.
_PASSWORD_MIN = 8
_PASSWORD_MAX = 72


def validate_register(data):
    """Return a list of validation errors for a register payload ([] if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]
    errors = []
    if not _is_non_empty_string(data.get("username")):
        errors.append("`username` is required and cannot be empty.")

    email = data.get("email")
    if not _is_non_empty_string(email):
        errors.append("`email` is required and cannot be empty.")
    elif not _EMAIL_RE.match(email):
        errors.append("`email` must be a valid email address.")

    password = data.get("password")
    if not isinstance(password, str) or password == "":
        errors.append("`password` is required and cannot be empty.")
    elif not (_PASSWORD_MIN <= len(password) <= _PASSWORD_MAX):
        errors.append(f"`password` must be between {_PASSWORD_MIN} and {_PASSWORD_MAX} characters.")

    # `role` is optional; when present it must be a non-empty string. Existence
    # of the role is checked against the DB in the handler.
    if "role" in data and not _is_non_empty_string(data.get("role")):
        errors.append("`role` must be a non-empty string when provided.")

    return errors


def validate_login(data):
    """Return a list of validation errors for a login payload ([] if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]
    errors = []
    if not _is_non_empty_string(data.get("username")) and not _is_non_empty_string(data.get("email")):
        errors.append("A `username` or `email` is required.")
    if not isinstance(data.get("password"), str) or data.get("password") == "":
        errors.append("`password` is required and cannot be empty.")
    return errors


def _is_non_empty_string(value):
    return isinstance(value, str) and value.strip() != ""
