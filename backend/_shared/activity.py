"""
Shared activity-log helpers for backend services.

Canonical source of truth. Propagated into each service folder by
bin/sync-shared.sh. Edit this file — never the generated copies.

Every service calls record() after a successful create/update/delete. Logging is
strictly best-effort: record() (and the actor/name helpers) never raise, so a
logging failure can never break the CRUD operation that already committed.
"""

import logging
from datetime import date, datetime
from decimal import Decimal

logger = logging.getLogger()

# Fields never worth diffing on an update.
_IGNORE = ("id", "created_at", "updated_at")


def _jsonable(value):
    """Coerce DB values into JSON-storable primitives for the `changes` column."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def diff(before, after, ignore=_IGNORE):
    """Field-level changes between two entity rows: [{field, old, new}]."""
    before = before or {}
    after = after or {}
    changes = []
    for key, new_val in after.items():
        if key in ignore:
            continue
        old_val = before.get(key)
        if old_val != new_val:
            changes.append({"field": key, "old": _jsonable(old_val), "new": _jsonable(new_val)})
    return changes


def actor(event):
    """
    Best-effort acting user {id, username} from the request's bearer token.
    Returns {id: None, username: None} when there is no valid token (e.g. public
    self-registration). Never raises.
    """
    try:
        import auth  # shared module, present alongside this one
        headers = event.get("headers") or {}
        raw = None
        for key, val in headers.items():
            if isinstance(key, str) and key.lower() == "authorization":
                raw = val
                break
        if not raw:
            return {"id": None, "username": None}
        claims = auth.decode_token(raw.split()[1])
        return {"id": int(claims["sub"]), "username": claims.get("username")}
    except Exception:
        return {"id": None, "username": None}


def record(acting, action, entity_type, entity_id, entity_name, changes=None):
    """
    Insert one activity_log row. Swallows all errors — an audit-log failure must
    never propagate into (and fail) the CRUD operation that already succeeded.
    """
    try:
        from postgres_service import execute
        from psycopg.types.json import Json

        acting = acting or {}
        execute(
            "INSERT INTO activity_log "
            "(user_id, username, action, entity_type, entity_id, entity_name, changes) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                acting.get("id"),
                acting.get("username"),
                action,
                entity_type,
                entity_id,
                entity_name,
                Json(changes) if changes else None,
            ),
        )
    except Exception as e:  # never let logging break the operation
        logger.warning("activity_log write failed (%s %s %s): %s", action, entity_type, entity_id, e)
