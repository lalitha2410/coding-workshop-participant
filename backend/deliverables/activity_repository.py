# ============================================================
# GENERATED FILE - DO NOT EDIT
# Source of truth: backend/_shared/activity_repository.py
# Regenerate with: bin/sync-shared.sh
# ============================================================
"""
Read-side data access for the activity log (audit trail).

Lives in the shared layer but is only wired into the auth service, which hosts
GET /auth/activity. RBAC is enforced *in the query*: callers who may not see
user-management history pass include_user_entities=False and the rows for
entity_type='user' are excluded at the SQL level (not just hidden in the UI).
"""

from postgres_service import execute

# Columns exposed to the API. created_at is serialized by the handler's json default.
_COLUMNS = "id, user_id, username, action, entity_type, entity_id, entity_name, changes, created_at"


def list_activity(entity_type=None, action=None, user_id=None,
                  include_user_entities=True, limit=50, offset=0):
    """
    Return a page of activity-log entries, NEWEST FIRST.

    Filters (all optional): entity_type, action, user_id. When
    include_user_entities is False, entries for entity_type='user' are excluded
    at the SQL level — this is the Manager-vs-Admin visibility rule.

    Shape: {"items": [...], "total": <int>, "limit": <int>, "offset": <int>}.
    """
    clauses, params = [], []
    if not include_user_entities:
        clauses.append("entity_type <> 'user'")
    if entity_type:
        clauses.append("entity_type = %s")
        params.append(entity_type)
    if action:
        clauses.append("action = %s")
        params.append(action)
    if user_id is not None:
        clauses.append("user_id = %s")
        params.append(user_id)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    total = execute(f"SELECT COUNT(*) AS n FROM activity_log{where}", params, fetch="one")["n"]
    items = execute(
        f"SELECT {_COLUMNS} FROM activity_log{where} "
        f"ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
        params + [limit, offset],
        fetch="all",
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}
