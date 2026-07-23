"""
Security tests — authentication, the RBAC gate, and token handling.

Three layers, all against a mocked repository (no DB) with explicit bearer tokens:
  * the shared `auth` module itself (passwords, JWT, role_can, require_*), which
    is the auth/permissions/token surface every service shares;
  * the auth handler's authn/RBAC decisions (register elevation, /auth/me token
    validity, and the /auth/users management gate);
  * the GET /auth/activity RBAC gate (list_activity mocked via the spy_list fixture).
"""

import json
import time
from datetime import datetime

import jwt
import pytest

import auth
import function
from testkit import parse_body, bearer

pytestmark = pytest.mark.security


# ===========================================================================
# Shared auth module — passwords, JWT, authenticate, RBAC
# ===========================================================================

def _event_with_token(token):
    return {"headers": {"Authorization": f"Bearer {token}"}}


# ---------------------------------------------------------------------------
# Password hashing / verification
# ---------------------------------------------------------------------------

def test_hash_is_not_plaintext_and_is_bcrypt():
    hashed = auth.hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")


def test_verify_correct_and_incorrect_password():
    hashed = auth.hash_password("s3cret-password")
    assert auth.verify_password("s3cret-password", hashed) is True
    assert auth.verify_password("wrong-password", hashed) is False


def test_hash_is_salted_unique_per_call():
    assert auth.hash_password("same") != auth.hash_password("same")


def test_verify_handles_malformed_hash():
    assert auth.verify_password("whatever", "not-a-real-hash") is False
    assert auth.verify_password(None, "x") is False


# ---------------------------------------------------------------------------
# JWT create / decode / authenticate
# ---------------------------------------------------------------------------

def test_token_round_trip_carries_claims():
    token = auth.create_token({"sub": "1", "username": "ada", "role": "Admin"})
    claims = auth.decode_token(token)
    assert claims["sub"] == "1"
    assert claims["username"] == "ada"
    assert claims["role"] == "Admin"
    assert "exp" in claims and "iat" in claims


def test_authenticate_returns_principal():
    token = auth.create_token({"sub": "7", "username": "bob", "role": "Viewer"})
    principal = auth.authenticate(_event_with_token(token))
    assert principal["sub"] == "7"
    assert principal["role"] == "Viewer"


def test_authenticate_missing_header_raises_401():
    with pytest.raises(auth.Unauthorized):
        auth.authenticate({"headers": {}})


def test_authenticate_malformed_header_raises_401():
    with pytest.raises(auth.Unauthorized):
        auth.authenticate({"headers": {"Authorization": "Token abc"}})


def test_authenticate_header_is_case_insensitive():
    token = auth.create_token({"sub": "1", "username": "ada", "role": "Admin"})
    principal = auth.authenticate({"headers": {"authorization": f"bearer {token}"}})
    assert principal["role"] == "Admin"


def test_authenticate_expired_token_raises_401():
    token = auth.create_token({"sub": "1", "role": "Admin"}, expires_in=-10)
    with pytest.raises(auth.Unauthorized):
        auth.authenticate(_event_with_token(token))


def test_authenticate_invalid_signature_raises_401():
    # Token signed with a different secret must not validate.
    forged = jwt.encode({"sub": "1", "role": "Admin", "exp": int(time.time()) + 60},
                        "some-other-secret", algorithm="HS256")
    with pytest.raises(auth.Unauthorized):
        auth.authenticate(_event_with_token(forged))


def test_authenticate_garbage_token_raises_401():
    with pytest.raises(auth.Unauthorized):
        auth.authenticate(_event_with_token("not.a.jwt"))


def test_autherror_renders_response():
    err = auth.Forbidden("nope")
    resp = err.response
    assert resp["statusCode"] == 403
    assert "nope" in resp["body"]


# ---------------------------------------------------------------------------
# RBAC matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role,action,expected", [
    ("Viewer", auth.READ, True),
    ("Viewer", auth.CREATE, False),
    ("Viewer", auth.DELETE, False),
    ("Contributor", auth.CREATE, True),
    ("Contributor", auth.UPDATE, True),
    ("Contributor", auth.DELETE, False),
    ("Manager", auth.DELETE, True),
    ("Manager", auth.MANAGE_USERS, False),
    ("Admin", auth.DELETE, True),
    ("Admin", auth.MANAGE_USERS, True),
    ("Nonexistent", auth.READ, False),
])
def test_role_can(role, action, expected):
    assert auth.role_can(role, action) is expected


def test_require_permission_allows_and_blocks():
    contributor = {"role": "Contributor"}
    auth.require_permission(contributor, auth.CREATE)  # no raise
    with pytest.raises(auth.Forbidden):
        auth.require_permission(contributor, auth.DELETE)


def test_require_permission_viewer_blocked_from_create():
    with pytest.raises(auth.Forbidden):
        auth.require_permission({"role": "Viewer"}, auth.CREATE)


def test_require_role_allows_and_blocks():
    auth.require_role({"role": "Admin"}, "Admin", "Manager")  # no raise
    with pytest.raises(auth.Forbidden):
        auth.require_role({"role": "Viewer"}, "Admin", "Manager")


# ---------------------------------------------------------------------------
# Fail-safe principal validation (unknown role / deleted user)
# ---------------------------------------------------------------------------

def test_authenticate_unknown_role_raises_403():
    token = auth.create_token({"sub": "1", "username": "x", "role": "Wizard"})
    with pytest.raises(auth.Forbidden):
        auth.authenticate(_event_with_token(token))


def test_authenticate_deleted_user_raises_401():
    token = auth.create_token({"sub": "5", "username": "gone", "role": "Admin"})
    with pytest.raises(auth.Unauthorized):
        auth.authenticate(_event_with_token(token), user_exists=lambda uid: False)


def test_authenticate_existing_user_passes():
    token = auth.create_token({"sub": "5", "username": "here", "role": "Admin"})
    claims = auth.authenticate(_event_with_token(token), user_exists=lambda uid: True)
    assert claims["role"] == "Admin"


def test_authenticate_non_integer_subject_raises_401():
    token = auth.create_token({"sub": "not-an-int", "role": "Admin"})
    with pytest.raises(auth.Unauthorized):
        auth.authenticate(_event_with_token(token), user_exists=lambda uid: True)


def test_authorize_request_enforces_user_exists():
    token = auth.create_token({"sub": "5", "role": "Admin"})
    with pytest.raises(auth.Unauthorized):
        auth.authorize_request(_event_with_token(token), "GET", user_exists=lambda uid: False)


def test_authorize_request_unknown_role_raises_403():
    token = auth.create_token({"sub": "1", "role": "Ghost"})
    with pytest.raises(auth.Forbidden):
        auth.authorize_request(_event_with_token(token), "GET")


def test_valid_roles_are_exactly_the_four():
    assert auth.VALID_ROLES == {"Admin", "Manager", "Contributor", "Viewer"}


# ===========================================================================
# Handler-level authentication & RBAC (repository mocked)
# ===========================================================================

VIEWER_USER = {
    "id": 1, "username": "ada", "email": "ada@example.com",
    "role": "Viewer", "created_at": datetime(2026, 1, 1, 12, 0, 0),
}


# ---- register: role-elevation gate ----

def test_register_elevated_role_without_token_returns_403(repo):
    repo.set("create_user", VIEWER_USER)  # must not be reached
    event = {"httpMethod": "POST", "path": "/auth/register",
             "body": json.dumps({"username": "mgr", "email": "mgr@example.com",
                                  "password": "password123", "role": "Manager"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 403
    assert "create_user" not in repo.calls


def test_register_elevated_role_as_non_admin_returns_403(repo):
    repo.set("create_user", VIEWER_USER)  # must not be reached
    event = {"httpMethod": "POST", "path": "/auth/register",
             "headers": bearer("Manager", sub="9"),
             "body": json.dumps({"username": "x", "email": "x@example.com",
                                  "password": "password123", "role": "Admin"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 403
    assert "create_user" not in repo.calls


def test_register_elevated_role_as_admin_succeeds(repo):
    manager_user = {**VIEWER_USER, "role": "Manager"}
    repo.set("get_role_by_name", {"id": 2, "name": "Manager"})
    repo.set("create_user", manager_user)
    event = {"httpMethod": "POST", "path": "/auth/register",
             "headers": bearer("Admin", sub="1"),
             "body": json.dumps({"username": "mgr", "email": "mgr@example.com",
                                  "password": "password123", "role": "Manager"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 201
    assert parse_body(resp)["role"] == "Manager"


# ---- me: token validity ----

def test_me_without_token_returns_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/auth/me", "headers": {}})
    assert resp["statusCode"] == 401


def test_me_expired_token_returns_401(repo):
    token = auth.create_token({"sub": "1", "role": "Viewer"}, expires_in=-5)
    event = {"httpMethod": "GET", "path": "/auth/me",
             "headers": {"Authorization": f"Bearer {token}"}}
    resp = function.handler(event)
    assert resp["statusCode"] == 401


def test_me_deleted_user_returns_401(repo):
    repo.set("get_user_by_id", None)
    token = auth.create_token({"sub": "999", "role": "Viewer"})
    event = {"httpMethod": "GET", "path": "/auth/me",
             "headers": {"Authorization": f"Bearer {token}"}}
    resp = function.handler(event)
    assert resp["statusCode"] == 401


def test_me_bogus_role_token_returns_403(repo):
    # A validly-signed token carrying an unrecognized role must be denied (403).
    token = auth.create_token({"sub": "1", "username": "x", "role": "Wizard"})
    event = {"httpMethod": "GET", "path": "/auth/me",
             "headers": {"Authorization": f"Bearer {token}"}}
    resp = function.handler(event)
    assert resp["statusCode"] == 403


# ---- /auth/users management gate ----

def test_list_users_viewer_403(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "GET", "path": "/auth/users", "headers": bearer("Viewer")})
    assert resp["statusCode"] == 403


def test_list_users_no_token_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/auth/users"})
    assert resp["statusCode"] == 401


def test_change_role_viewer_403(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5/role", "headers": bearer("Viewer"),
                             "body": json.dumps({"role": "Manager"})})
    assert resp["statusCode"] == 403


def test_delete_user_manager_403(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "DELETE", "path": "/auth/users/5", "headers": bearer("Manager")})
    assert resp["statusCode"] == 403


def test_update_user_viewer_403(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5", "headers": bearer("Viewer"),
                             "body": json.dumps({"username": "ok"})})
    assert resp["statusCode"] == 403


def test_update_user_no_token_401(repo):
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5", "body": json.dumps({"username": "ok"})})
    assert resp["statusCode"] == 401


# ===========================================================================
# GET /auth/activity — RBAC gate (list_activity mocked)
# ===========================================================================

def _get(path, headers, query=None):
    evt = {"httpMethod": "GET", "path": path, "headers": headers}
    if query:
        evt["queryStringParameters"] = query
    return function.handler(evt)


@pytest.fixture
def present_user(monkeypatch):
    """Treat the token subject as an existing user (the gate checks the DB)."""
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: True)


@pytest.fixture
def spy_list(monkeypatch):
    """Replace list_activity with a spy that records its kwargs."""
    calls = {}

    def _fake(**kwargs):
        calls.update(kwargs)
        return {"items": [], "total": 0, "limit": kwargs["limit"], "offset": kwargs["offset"]}

    monkeypatch.setattr(function, "list_activity", _fake)
    return calls


@pytest.mark.parametrize("role", ["Viewer", "Contributor"])
def test_viewer_and_contributor_get_403(present_user, spy_list, role):
    resp = _get("/auth/activity", bearer(role))
    assert resp["statusCode"] == 403


def test_manager_is_allowed_but_hides_user_entities(present_user, spy_list):
    resp = _get("/auth/activity", bearer("Manager"))
    assert resp["statusCode"] == 200
    # The Manager-vs-Admin rule is pushed into the query, not the UI.
    assert spy_list["include_user_entities"] is False


def test_admin_sees_everything(present_user, spy_list):
    resp = _get("/auth/activity", bearer("Admin"))
    assert resp["statusCode"] == 200
    assert spy_list["include_user_entities"] is True


def test_filters_are_passed_through(present_user, spy_list):
    _get("/auth/activity", bearer("Admin"),
         query={"entity_type": "project", "action": "updated", "user": "7"})
    assert spy_list["entity_type"] == "project"
    assert spy_list["action"] == "updated"
    assert spy_list["user_id"] == 7


def test_activity_requires_authentication():
    # No headers at all -> the auth gate rejects before RBAC.
    resp = function.handler({"httpMethod": "GET", "path": "/auth/activity", "headers": {}})
    assert resp["statusCode"] in (401, 403)


def test_activity_rejects_non_get():
    resp = function.handler({"httpMethod": "POST", "path": "/auth/activity", "headers": bearer("Admin")})
    assert resp["statusCode"] == 405
