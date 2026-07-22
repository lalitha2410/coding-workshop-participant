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
