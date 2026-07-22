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


def list_resources(search=None):
    """
    Return all resources, optionally filtered by a case-insensitive search that
    matches either the name or the title.
    """
    sql = f"SELECT {_COLUMNS} FROM resources"
    params = []
    if search:
        sql += " WHERE name ILIKE %s OR title ILIKE %s"
        like = f"%{search}%"
        params = [like, like]
    sql += " ORDER BY id"
    return execute(sql, params, fetch="all")


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
    sql = "DELETE FROM resources WHERE id = %s RETURNING id"
    return execute(sql, (resource_id,), fetch="one")
