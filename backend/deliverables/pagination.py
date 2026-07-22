# ============================================================
# GENERATED FILE - DO NOT EDIT
# Source of truth: backend/_shared/pagination.py
# Regenerate with: bin/sync-shared.sh
# ============================================================
"""
Shared pagination parsing/validation for list endpoints.

Canonical source of truth. Propagated into each backend service folder by
bin/sync-shared.sh. Edit this file — never the generated copies under
backend/<service>/pagination.py.

List handlers call parse_pagination(query) to turn optional ?limit / ?offset
query params into validated (limit, offset), then return a uniform envelope:
    {"items": [...], "total": <int>, "limit": <int>, "offset": <int>}
"""

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class PaginationError(ValueError):
    """Raised for invalid limit/offset query parameters (maps to HTTP 400)."""


def parse_pagination(query):
    """
    Parse and validate ?limit and ?offset from a query-params dict.

    Returns (limit, offset). `limit` defaults to DEFAULT_LIMIT and is capped at
    MAX_LIMIT; `offset` defaults to 0. Raises PaginationError for non-integer or
    negative values.
    """
    query = query or {}
    limit = _parse_non_negative(query.get("limit"), DEFAULT_LIMIT, "limit")
    offset = _parse_non_negative(query.get("offset"), 0, "offset")
    if limit > MAX_LIMIT:
        limit = MAX_LIMIT  # cap to a sane maximum rather than reject
    return limit, offset


def _parse_non_negative(value, default, name):
    if value is None or value == "":
        return default
    # Bools are ints in Python; reject them as invalid pagination values.
    if isinstance(value, bool):
        raise PaginationError(f"`{name}` must be a non-negative integer.")
    try:
        parsed = int(value.strip()) if isinstance(value, str) else int(value)
    except (TypeError, ValueError):
        raise PaginationError(f"`{name}` must be a non-negative integer.")
    if parsed < 0:
        raise PaginationError(f"`{name}` must be a non-negative integer.")
    return parsed
