"""
Validation for allocation create/update payloads.

Each validator returns a list of human-readable error strings (empty list when
the payload is valid), so the handler can turn any non-empty result into a 400.
Rules mirror the `allocations` table constraints in backend/db/schema.sql.

Note: these checks are pure (no database). The dual foreign keys (resource_id,
project_id must exist) and the UNIQUE (resource_id, project_id) constraint are
enforced at the handler/DB layer and surfaced as 400s.
"""

from datetime import date


def validate_create(data):
    """Return a list of validation errors for a create payload ([] if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]
    errors = []
    if not _is_integer(data.get("resource_id")):
        errors.append("`resource_id` is required and must be an integer.")
    if not _is_integer(data.get("project_id")):
        errors.append("`project_id` is required and must be an integer.")
    errors.extend(_validate_common(data))
    return errors


def validate_update(data):
    """Return a list of validation errors for a (partial) update payload ([] if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]
    errors = []
    if "resource_id" in data and not _is_integer(data.get("resource_id")):
        errors.append("`resource_id` must be an integer.")
    if "project_id" in data and not _is_integer(data.get("project_id")):
        errors.append("`project_id` must be an integer.")
    errors.extend(_validate_common(data))
    return errors


def _validate_common(data):
    """Range/format/date-order checks shared by create and update payloads."""
    errors = []

    pct = data.get("allocation_pct")
    if pct is not None:
        if not _is_integer(pct):
            errors.append("`allocation_pct` must be an integer.")
        elif not (0 <= int(pct) <= 100):
            errors.append("`allocation_pct` must be between 0 and 100.")

    start = data.get("start_date")
    end = data.get("end_date")
    for field, value in (("start_date", start), ("end_date", end)):
        if value is not None and _coerce_date(value) is None:
            errors.append(f"`{field}` must be a valid date (YYYY-MM-DD).")

    # If both dates are present and valid, end must not precede start.
    start_d, end_d = _coerce_date(start), _coerce_date(end)
    if start_d is not None and end_d is not None and end_d < start_d:
        errors.append("`end_date` must not be before `start_date`.")

    return errors


def _is_integer(value):
    # Bools are ints in Python; reject them explicitly.
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    try:
        int(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _coerce_date(value):
    """Return a date for a date/ISO-string value, or None if not a valid date."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
