"""
Data-access layer for the `users` and `roles` tables.

Each function is a thin, parameterized SQL wrapper over postgres_service.execute
and returns plain dicts (rows). User rows are joined to `roles` so callers see
the role *name*. Public queries never expose password_hash.
"""

import psycopg

from postgres_service import execute


class DuplicateUserError(Exception):
    """Raised when a username or email already exists (UNIQUE violation)."""


# Public user projection (no password_hash), with the role name joined in.
_PUBLIC = "u.id, u.username, u.email, r.name AS role, u.created_at"


def get_user_by_id(user_id):
    """Return the public view of a user by id, or None if not found."""
    sql = f"""
        SELECT {_PUBLIC}
        FROM users u JOIN roles r ON u.role_id = r.id
        WHERE u.id = %s
    """
    return execute(sql, (user_id,), fetch="one")


def get_user_for_login(identifier):
    """
    Return a user (including password_hash) matched by username OR email.

    Used only by the login flow; callers must not leak password_hash further.
    """
    sql = """
        SELECT u.id, u.username, u.email, u.password_hash, r.name AS role
        FROM users u JOIN roles r ON u.role_id = r.id
        WHERE u.username = %s OR u.email = %s
        LIMIT 1
    """
    return execute(sql, (identifier, identifier), fetch="one")


def create_user(username, email, password_hash, role_id):
    """Insert a new user and return the public view.

    Raises DuplicateUserError if the username or email is already taken.
    """
    sql = "INSERT INTO users (username, email, password_hash, role_id) VALUES (%s, %s, %s, %s) RETURNING id"
    try:
        row = execute(sql, (username, email, password_hash, role_id), fetch="one")
    except psycopg.errors.UniqueViolation:
        raise DuplicateUserError(username)
    return get_user_by_id(row["id"])


def get_role_by_name(name):
    """Return a role row {id, name} by name, or None if it does not exist."""
    return execute("SELECT id, name FROM roles WHERE name = %s", (name,), fetch="one")


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------

def list_users(search=None, limit=50, offset=0):
    """
    Return a page of users (public view) plus pagination info. Optional `search`
    matches username or email, case-insensitively.

    Shape: {"items": [...], "total": <int>, "limit": <int>, "offset": <int>}.
    """
    where, params = "", []
    if search:
        where = " WHERE u.username ILIKE %s OR u.email ILIKE %s"
        like = f"%{search}%"
        params = [like, like]
    total = execute(f"SELECT COUNT(*) AS n FROM users u{where}", params, fetch="one")["n"]
    items = execute(
        f"SELECT {_PUBLIC} FROM users u JOIN roles r ON u.role_id = r.id{where} ORDER BY u.id LIMIT %s OFFSET %s",
        params + [limit, offset],
        fetch="all",
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def update_user_role(user_id, role_id):
    """Set a user's role; return the updated public view, or None if not found."""
    row = execute("UPDATE users SET role_id = %s WHERE id = %s RETURNING id", (role_id, user_id), fetch="one")
    if row is None:
        return None
    return get_user_by_id(user_id)


def update_user_details(user_id, username=None, email=None):
    """
    Update a user's username and/or email (partial via COALESCE); return the
    updated public view, or None if the user does not exist.

    Raises DuplicateUserError if the new username/email collides with another row.
    """
    sql = """
        UPDATE users SET
            username = COALESCE(%s, username),
            email    = COALESCE(%s, email)
        WHERE id = %s
        RETURNING id
    """
    try:
        row = execute(sql, (username, email, user_id), fetch="one")
    except psycopg.errors.UniqueViolation:
        raise DuplicateUserError(username or email)
    if row is None:
        return None
    return get_user_by_id(user_id)


def delete_user(user_id):
    """Delete a user; return {"id": ...} or None if the user did not exist."""
    return execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,), fetch="one")
