"""
Validation for project create/update payloads.

Each validator returns a list of human-readable error strings (empty list when
the payload is valid), so the handler can turn any non-empty result into a 400.
Rules mirror the `projects` table constraints in backend/db/schema.sql.
"""

from datetime import date

# Allowed values for projects.status (matches the CHECK constraint in the schema).
VALID_STATUSES = ("planning", "active", "on_hold", "completed", "cancelled")

# Numeric and date fields, used for format checks shared by create and update.
_NUMERIC_FIELDS = ("budget_planned", "budget_consumed")
_DATE_FIELDS = ("start_date", "end_date", "deadline")


def validate_create(data):
    """Return a list of validation errors for a create payload ([] if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]
    errors = []
    if not _is_non_empty_string(data.get("name")):
        errors.append("`name` is required and cannot be empty.")
    errors.extend(_validate_common(data))
    return errors


def validate_update(data):
    """Return a list of validation errors for a (partial) update payload ([] if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]
    errors = []
    # name is optional on update, but if present it must be non-empty.
    if "name" in data and not _is_non_empty_string(data.get("name")):
        errors.append("`name` cannot be empty.")
    errors.extend(_validate_common(data))
    return errors


def _validate_common(data):
    """Format/enum checks that apply to both create and update payloads."""
    errors = []

    status = data.get("status")
    if status is not None and status not in VALID_STATUSES:
        errors.append(f"`status` must be one of: {', '.join(VALID_STATUSES)}.")

    for field in _NUMERIC_FIELDS:
        value = data.get(field)
        if value is not None and not _is_number(value):
            errors.append(f"`{field}` must be a number.")

    for field in _DATE_FIELDS:
        value = data.get(field)
        if value is not None and not _is_date(value):
            errors.append(f"`{field}` must be a valid date (YYYY-MM-DD).")

    return errors


def _is_non_empty_string(value):
    return isinstance(value, str) and value.strip() != ""


def _is_number(value):
    # Bools are ints in Python; reject them explicitly as invalid budgets.
    if isinstance(value, bool):
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _is_date(value):
    if isinstance(value, date):
        return True
    try:
        date.fromisoformat(str(value))
        return True
    except (TypeError, ValueError):
        return False
