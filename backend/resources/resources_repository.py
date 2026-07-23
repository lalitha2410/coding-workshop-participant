"""
Data-access layer for the `resources` table.

Each function is a thin, parameterized SQL wrapper over postgres_service.execute
and returns plain dicts (rows) so the handler layer stays free of DB concerns.

The `email` column has a UNIQUE constraint; create/update translate the database
UniqueViolation into a DuplicateEmailError so the handler can return a clean 400.
"""

import psycopg

from postgres_service import execute


class DuplicateEmailError(Exception):
    """Raised when a resource's email would violate the UNIQUE constraint.

    str(err) is the offending email address.
    """


# Business columns returned to API clients (resources has no updated_at).
_COLUMNS = "id, name, email, title, created_at"


def _resource_filters(search):
    """Build the shared WHERE clause + params for list/count."""
    if search:
        like = f"%{search}%"
        return " WHERE name ILIKE %s OR title ILIKE %s", [like, like]
    return "", []


def list_resources(search=None, limit=50, offset=0):
    """
    Return a page of resources plus pagination info. The optional case-insensitive
    `search` matches either the name or the title.

    Shape: {"items": [...], "total": <int>, "limit": <int>, "offset": <int>}.
    `total` counts all rows matching the filter, ignoring limit/offset.
    """
    where, params = _resource_filters(search)
    total = execute(f"SELECT COUNT(*) AS n FROM resources{where}", params, fetch="one")["n"]
    items = execute(
        f"SELECT {_COLUMNS} FROM resources{where} ORDER BY id LIMIT %s OFFSET %s",
        params + [limit, offset],
        fetch="all",
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_resource(resource_id):
    """Return a single resource by id, or None if it does not exist."""
    sql = f"SELECT {_COLUMNS} FROM resources WHERE id = %s"
    return execute(sql, (resource_id,), fetch="one")


def create_resource(data):
    """Insert a new resource and return the created row.

    Raises DuplicateEmailError if the email is already taken.
    """
    sql = f"""
        INSERT INTO resources (name, email, title)
        VALUES (%s, %s, %s)
        RETURNING {_COLUMNS}
    """
    params = (data.get("name"), data.get("email"), data.get("title"))
    try:
        return execute(sql, params, fetch="one")
    except psycopg.errors.UniqueViolation:
        raise DuplicateEmailError(data.get("email"))


def update_resource(resource_id, data):
    """
    Partially update a resource and return the updated row (None if not found).

    COALESCE keeps the existing column value whenever the incoming field is None,
    so callers only need to send the fields they want to change. (The resources
    table has no updated_at column, so none is set here.)

    Raises DuplicateEmailError if the new email is already taken by another row.
    """
    sql = f"""
        UPDATE resources SET
            name  = COALESCE(%s, name),
            email = COALESCE(%s, email),
            title = COALESCE(%s, title)
        WHERE id = %s
        RETURNING {_COLUMNS}
    """
    params = (data.get("name"), data.get("email"), data.get("title"), resource_id)
    try:
        return execute(sql, params, fetch="one")
    except psycopg.errors.UniqueViolation:
        raise DuplicateEmailError(data.get("email"))


def delete_resource(resource_id):
    """Delete a resource; return the deleted row ({"id": ...}) or None if not found."""
    sql = "DELETE FROM resources WHERE id = %s RETURNING id, name"
    return execute(sql, (resource_id,), fetch="one")
