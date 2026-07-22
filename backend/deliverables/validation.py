"""
Validation for deliverable create/update payloads.

Each validator returns a list of human-readable error strings (empty list when
the payload is valid), so the handler can turn any non-empty result into a 400.
Rules mirror the `deliverables` table constraints in backend/db/schema.sql.

Note: these checks are pure (no database). Verifying that the referenced
project_id actually exists is a cross-entity check done in the handler via
deliverables_repository.project_exists.
"""

from datetime import date

# Allowed values for deliverables.status (matches the CHECK constraint).
VALID_STATUSES = ("not_started", "in_progress", "blocked", "completed")


def validate_create(data):
    """Return a list of validation errors for a create payload ([] if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]
    errors = []
    if not _is_integer(data.get("project_id")):
        errors.append("`project_id` is required and must be an integer.")
    if not _is_non_empty_string(data.get("name")):
        errors.append("`name` is required and cannot be empty.")
    errors.extend(_validate_common(data))
    return errors


def validate_update(data):
    """Return a list of validation errors for a (partial) update payload ([] if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]
    errors = []
    # Fields are optional on update, but must be well-formed when present.
    if "project_id" in data and not _is_integer(data.get("project_id")):
        errors.append("`project_id` must be an integer.")
    if "name" in data and not _is_non_empty_string(data.get("name")):
        errors.append("`name` cannot be empty.")
    errors.extend(_validate_common(data))
    return errors


def _validate_common(data):
    """Format/enum/range checks that apply to both create and update payloads."""
    errors = []

    status = data.get("status")
    if status is not None and status not in VALID_STATUSES:
        errors.append(f"`status` must be one of: {', '.join(VALID_STATUSES)}.")

    pct = data.get("completion_pct")
    if pct is not None:
        if not _is_integer(pct):
            errors.append("`completion_pct` must be an integer.")
        elif not (0 <= int(pct) <= 100):
            errors.append("`completion_pct` must be between 0 and 100.")

    due_date = data.get("due_date")
    if due_date is not None and not _is_date(due_date):
        errors.append("`due_date` must be a valid date (YYYY-MM-DD).")

    return errors


def _is_non_empty_string(value):
    return isinstance(value, str) and value.strip() != ""


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


def _is_date(value):
    if isinstance(value, date):
        return True
    try:
        date.fromisoformat(str(value))
        return True
    except (TypeError, ValueError):
        return False
