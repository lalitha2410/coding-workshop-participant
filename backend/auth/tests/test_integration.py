"""
Integration tests for the auth service against a real local PostgreSQL.

Exercises the full register -> login -> me flow end to end through the handler,
plus role-assignment RBAC. Uses distinctive `.invalid` usernames/emails and
cleans them up. Auto-skips when the DB / users+roles schema is unavailable.

Run against the local dev database with the schema loaded:
    IS_LOCAL=true pytest backend/auth/tests/test_integration.py
"""

import json

import pytest

import auth
import function
import postgres_service


def _database_ready():
    try:
        postgres_service.execute("SELECT 1 FROM users LIMIT 1", fetch="one")
        postgres_service.execute("SELECT 1 FROM roles LIMIT 1", fetch="one")
        return True
    except Exception:
        postgres_service.PG_CONN = None
        return False


pytestmark = pytest.mark.skipif(
    not _database_ready(),
    reason="local PostgreSQL with the users/roles schema is not available",
)

_USERNAMES = ("auth-it-viewer", "auth-it-admin", "auth-it-manager", "auth-it-dup")


def _cleanup():
    for username in _USERNAMES:
        postgres_service.execute("DELETE FROM users WHERE username = %s", (username,))


@pytest.fixture(autouse=True)
def clean_users():
    _cleanup()
    yield
    _cleanup()


def _post(path, body, headers=None):
    event = {"httpMethod": "POST", "path": path, "body": json.dumps(body)}
    if headers:
        event["headers"] = headers
    return function.handler(event)


def _get(path, headers=None):
    event = {"httpMethod": "GET", "path": path}
    if headers:
        event["headers"] = headers
    return function.handler(event)


def _seed_admin(username="auth-it-admin"):
    """Insert an Admin user directly (bootstraps the first Admin) and return id."""
    admin_role = postgres_service.execute("SELECT id FROM roles WHERE name = 'Admin'", fetch="one")
    row = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) VALUES (%s, %s, %s, %s) RETURNING id",
        (username, f"{username}@example-test.invalid", auth.hash_password("adminpass123"), admin_role["id"]),
        fetch="one",
    )
    return row["id"]


# ---------------------------------------------------------------------------
# register -> login -> me
# ---------------------------------------------------------------------------

def test_register_login_me_round_trip():
    reg = _post("/auth/register", {
        "username": "auth-it-viewer",
        "email": "auth-it-viewer@example-test.invalid",
        "password": "password123",
    })
    assert reg["statusCode"] == 201
    reg_body = json.loads(reg["body"])
    assert reg_body["role"] == "Viewer"
    assert "password_hash" not in reg_body

    login = _post("/auth/login", {"username": "auth-it-viewer", "password": "password123"})
    assert login["statusCode"] == 200
    token = json.loads(login["body"])["token"]

    me = _get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me["statusCode"] == 200
    me_body = json.loads(me["body"])
    assert me_body["username"] == "auth-it-viewer"
    assert me_body["role"] == "Viewer"


def test_login_can_use_email_identifier():
    _post("/auth/register", {
        "username": "auth-it-viewer",
        "email": "auth-it-viewer@example-test.invalid",
        "password": "password123",
    })
    login = _post("/auth/login", {"email": "auth-it-viewer@example-test.invalid", "password": "password123"})
    assert login["statusCode"] == 200


def test_register_duplicate_username_returns_400():
    body = {"username": "auth-it-dup", "email": "auth-it-dup@example-test.invalid", "password": "password123"}
    assert _post("/auth/register", body)["statusCode"] == 201
    dup = _post("/auth/register", body)
    assert dup["statusCode"] == 400
    assert "already in use" in json.loads(dup["body"])["error"]


def test_login_wrong_password_returns_401():
    _post("/auth/register", {
        "username": "auth-it-viewer",
        "email": "auth-it-viewer@example-test.invalid",
        "password": "password123",
    })
    login = _post("/auth/login", {"username": "auth-it-viewer", "password": "nope-nope-nope"})
    assert login["statusCode"] == 401


# ---------------------------------------------------------------------------
# RBAC on role assignment during registration
# ---------------------------------------------------------------------------

def test_elevated_role_requires_admin_token():
    # No token -> forbidden to self-assign Manager.
    resp = _post("/auth/register", {
        "username": "auth-it-manager",
        "email": "auth-it-manager@example-test.invalid",
        "password": "password123",
        "role": "Manager",
    })
    assert resp["statusCode"] == 403
    # And the user was not created.
    assert postgres_service.execute(
        "SELECT id FROM users WHERE username = %s", ("auth-it-manager",), fetch="one"
    ) is None


def test_me_after_user_deleted_returns_401():
    # Register + login, then delete the user out from under a still-valid token.
    _post("/auth/register", {
        "username": "auth-it-viewer",
        "email": "auth-it-viewer@example-test.invalid",
        "password": "password123",
    })
    login = _post("/auth/login", {"username": "auth-it-viewer", "password": "password123"})
    token = json.loads(login["body"])["token"]

    postgres_service.execute("DELETE FROM users WHERE username = %s", ("auth-it-viewer",))

    me = _get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me["statusCode"] == 401


def test_admin_can_create_manager():
    _seed_admin()
    login = _post("/auth/login", {"username": "auth-it-admin", "password": "adminpass123"})
    admin_token = json.loads(login["body"])["token"]

    resp = _post(
        "/auth/register",
        {
            "username": "auth-it-manager",
            "email": "auth-it-manager@example-test.invalid",
            "password": "password123",
            "role": "Manager",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp["statusCode"] == 201
    assert json.loads(resp["body"])["role"] == "Manager"
