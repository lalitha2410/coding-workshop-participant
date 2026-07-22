"""
Validation for resource create/update payloads.

Each validator returns a list of human-readable error strings (empty list when
the payload is valid), so the handler can turn any non-empty result into a 400.
Rules mirror the `resources` table constraints in backend/db/schema.sql.

Note: these checks are pure (no database). The UNIQUE email constraint is
enforced at the repository/DB layer and surfaced as a 400 by the handler.
"""

import re

# Pragmatic email check: non-empty local part, single @, dotted domain.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_create(data):
    """Return a list of validation errors for a create payload ([] if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]
    errors = []
    if not _is_non_empty_string(data.get("name")):
        errors.append("`name` is required and cannot be empty.")
    errors.extend(_validate_email(data, required=True))
    return errors


def validate_update(data):
    """Return a list of validation errors for a (partial) update payload ([] if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]
    errors = []
    if "name" in data and not _is_non_empty_string(data.get("name")):
        errors.append("`name` cannot be empty.")
    # email is optional on update, but must be valid when present.
    if "email" in data:
        errors.extend(_validate_email(data, required=True))
    return errors


def _validate_email(data, required):
    """Validate the email field; `required` controls the missing-value message."""
    email = data.get("email")
    if not _is_non_empty_string(email):
        return ["`email` is required and cannot be empty."] if required else []
    if not _EMAIL_RE.match(email):
        return ["`email` must be a valid email address."]
    return []


def _is_non_empty_string(value):
    return isinstance(value, str) and value.strip() != ""
