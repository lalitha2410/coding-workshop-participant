"""
Unit tests for the auth function.handler.

The users repository is monkeypatched; token/hash logic is exercised for real
(auth is stateless), so these run without a database.
"""

import json
from datetime import datetime

import pytest

import auth
import function
from users_repository import DuplicateUserError


def _body(response):
    raw = response["body"]
    return json.loads(raw) if raw else None


VIEWER_USER = {
    "id": 1, "username": "ada", "email": "ada@example.com",
    "role": "Viewer", "created_at": datetime(2026, 1, 1, 12, 0, 0),
}


@pytest.fixture
def repo(monkeypatch):
    calls = {}

    def record(name, return_value):
        def _fn(*args, **kwargs):
            calls[name] = {"args": args, "kwargs": kwargs}
            if isinstance(return_value, Exception):
                raise return_value
            return return_value
        return _fn

    class Repo:
        def set(self, name, return_value):
            monkeypatch.setattr(function, name, record(name, return_value))

        @property
        def calls(self):
            return calls

    return Repo()


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------

def test_register_default_viewer_returns_201(repo):
    repo.set("get_role_by_name", {"id": 4, "name": "Viewer"})
    repo.set("create_user", VIEWER_USER)
    event = {"httpMethod": "POST", "path": "/auth/register",
             "body": json.dumps({"username": "ada", "email": "ada@example.com", "password": "password123"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 201
    assert _body(resp)["role"] == "Viewer"
    # password must never be echoed back
    assert "password" not in _body(resp) and "password_hash" not in _body(resp)
    # role looked up was the default
    assert repo.calls["get_role_by_name"]["args"] == ("Viewer",)


def test_register_validation_error_returns_400(repo):
    event = {"httpMethod": "POST", "path": "/auth/register",
             "body": json.dumps({"username": "ada", "email": "bad", "password": "short"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "details" in _body(resp)


def test_register_duplicate_returns_400(repo):
    repo.set("get_role_by_name", {"id": 4, "name": "Viewer"})
    repo.set("create_user", DuplicateUserError("ada"))
    event = {"httpMethod": "POST", "path": "/auth/register",
             "body": json.dumps({"username": "ada", "email": "ada@example.com", "password": "password123"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "already in use" in _body(resp)["error"]


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
    token = auth.create_token({"sub": "9", "username": "mgr", "role": "Manager"})
    event = {"httpMethod": "POST", "path": "/auth/register",
             "headers": {"Authorization": f"Bearer {token}"},
             "body": json.dumps({"username": "x", "email": "x@example.com",
                                  "password": "password123", "role": "Admin"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 403
    assert "create_user" not in repo.calls


def test_register_elevated_role_as_admin_succeeds(repo):
    manager_user = {**VIEWER_USER, "role": "Manager"}
    repo.set("get_role_by_name", {"id": 2, "name": "Manager"})
    repo.set("create_user", manager_user)
    token = auth.create_token({"sub": "1", "username": "root", "role": "Admin"})
    event = {"httpMethod": "POST", "path": "/auth/register",
             "headers": {"Authorization": f"Bearer {token}"},
             "body": json.dumps({"username": "mgr", "email": "mgr@example.com",
                                  "password": "password123", "role": "Manager"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 201
    assert _body(resp)["role"] == "Manager"


def test_register_unknown_role_returns_400(repo):
    repo.set("get_role_by_name", None)
    token = auth.create_token({"sub": "1", "role": "Admin"})
    event = {"httpMethod": "POST", "path": "/auth/register",
             "headers": {"Authorization": f"Bearer {token}"},
             "body": json.dumps({"username": "x", "email": "x@example.com",
                                  "password": "password123", "role": "Wizard"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400
    assert "Unknown role" in _body(resp)["error"]


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------

def _login_row(password):
    return {
        "id": 1, "username": "ada", "email": "ada@example.com", "role": "Viewer",
        "password_hash": auth.hash_password(password),
    }


def test_login_success_returns_token(repo):
    repo.set("get_user_for_login", _login_row("password123"))
    event = {"httpMethod": "POST", "path": "/auth/login",
             "body": json.dumps({"username": "ada", "password": "password123"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    body = _body(resp)
    assert body["token_type"] == "Bearer"
    claims = auth.decode_token(body["token"])
    assert claims["username"] == "ada" and claims["role"] == "Viewer"
    assert "password_hash" not in body["user"]


def test_login_wrong_password_returns_401(repo):
    repo.set("get_user_for_login", _login_row("password123"))
    event = {"httpMethod": "POST", "path": "/auth/login",
             "body": json.dumps({"username": "ada", "password": "WRONG"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 401
    assert _body(resp)["error"] == "Invalid credentials."


def test_login_unknown_user_returns_401(repo):
    repo.set("get_user_for_login", None)
    event = {"httpMethod": "POST", "path": "/auth/login",
             "body": json.dumps({"email": "nobody@example.com", "password": "password123"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 401


def test_login_validation_error_returns_400(repo):
    event = {"httpMethod": "POST", "path": "/auth/login", "body": json.dumps({"password": "x"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 400


# ---------------------------------------------------------------------------
# me
# ---------------------------------------------------------------------------

def test_me_returns_current_user(repo):
    repo.set("get_user_by_id", VIEWER_USER)
    token = auth.create_token({"sub": "1", "username": "ada", "role": "Viewer"})
    event = {"httpMethod": "GET", "path": "/auth/me",
             "headers": {"Authorization": f"Bearer {token}"}}
    resp = function.handler(event)
    assert resp["statusCode"] == 200
    assert _body(resp)["username"] == "ada"
    assert repo.calls["get_user_by_id"]["args"] == (1,)


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


# ---------------------------------------------------------------------------
# routing / errors
# ---------------------------------------------------------------------------

def test_unknown_route_returns_404(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/auth/unknown"})
    assert resp["statusCode"] == 404


def test_wrong_method_returns_405(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/auth/login"})
    assert resp["statusCode"] == 405


def test_malformed_json_returns_400(repo):
    resp = function.handler({"httpMethod": "POST", "path": "/auth/register", "body": "{nope"})
    assert resp["statusCode"] == 400


def test_unexpected_error_returns_500(repo):
    repo.set("get_user_for_login", RuntimeError("db down"))
    event = {"httpMethod": "POST", "path": "/auth/login",
             "body": json.dumps({"username": "ada", "password": "password123"})}
    resp = function.handler(event)
    assert resp["statusCode"] == 500


# ---------------------------------------------------------------------------
# Admin user management  (/auth/users)
# ---------------------------------------------------------------------------

def _hdr(role, sub="1"):
    token = auth.create_token({"sub": sub, "username": "u", "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def bypass_user_check(monkeypatch):
    # The admin routes verify the token's user still exists (DB); bypass in unit tests.
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: True)


A_USER = {"id": 5, "username": "sam", "email": "sam@acme.test", "role": "Manager",
          "created_at": datetime(2026, 1, 1, 12, 0, 0)}


# ---- list ----

def test_list_users_admin_200(repo, bypass_user_check):
    repo.set("list_users", {"items": [A_USER], "total": 1, "limit": 50, "offset": 0})
    resp = function.handler({"httpMethod": "GET", "path": "/auth/users", "headers": _hdr("Admin")})
    assert resp["statusCode"] == 200
    body = _body(resp)
    assert body["items"][0]["username"] == "sam" and body["total"] == 1
    assert repo.calls["list_users"]["kwargs"] == {"search": None, "limit": 50, "offset": 0}


def test_list_users_search_passthrough(repo, bypass_user_check):
    repo.set("list_users", {"items": [], "total": 0, "limit": 50, "offset": 0})
    function.handler({"httpMethod": "GET", "path": "/auth/users", "headers": _hdr("Admin"),
                      "queryStringParameters": {"search": "sam"}})
    assert repo.calls["list_users"]["kwargs"]["search"] == "sam"


def test_list_users_viewer_403(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "GET", "path": "/auth/users", "headers": _hdr("Viewer")})
    assert resp["statusCode"] == 403


def test_list_users_no_token_401(repo):
    resp = function.handler({"httpMethod": "GET", "path": "/auth/users"})
    assert resp["statusCode"] == 401


def test_list_users_bad_pagination_400(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "GET", "path": "/auth/users", "headers": _hdr("Admin"),
                             "queryStringParameters": {"limit": "abc"}})
    assert resp["statusCode"] == 400


# ---- change role ----

def test_change_role_200(repo, bypass_user_check):
    repo.set("get_role_by_name", {"id": 2, "name": "Manager"})
    repo.set("update_user_role", {**A_USER, "role": "Manager"})
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5/role", "headers": _hdr("Admin"),
                             "body": json.dumps({"role": "Manager"})})
    assert resp["statusCode"] == 200
    assert _body(resp)["role"] == "Manager"


def test_change_role_invalid_role_400(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5/role", "headers": _hdr("Admin"),
                             "body": json.dumps({"role": "Wizard"})})
    assert resp["statusCode"] == 400
    assert "must be one of" in _body(resp)["error"]


def test_change_role_self_demotion_400(repo, bypass_user_check):
    # Admin (sub=5) trying to change user 5 (themselves) to Viewer -> blocked.
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5/role", "headers": _hdr("Admin", sub="5"),
                             "body": json.dumps({"role": "Viewer"})})
    assert resp["statusCode"] == 400
    assert "own role" in _body(resp)["error"]


def test_change_role_self_to_admin_ok(repo, bypass_user_check):
    # Setting your own role to Admin (a no-op) is allowed.
    repo.set("get_role_by_name", {"id": 1, "name": "Admin"})
    repo.set("update_user_role", {**A_USER, "id": 5, "role": "Admin"})
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5/role", "headers": _hdr("Admin", sub="5"),
                             "body": json.dumps({"role": "Admin"})})
    assert resp["statusCode"] == 200


def test_change_role_not_found_404(repo, bypass_user_check):
    repo.set("get_role_by_name", {"id": 2, "name": "Manager"})
    repo.set("update_user_role", None)
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/999/role", "headers": _hdr("Admin"),
                             "body": json.dumps({"role": "Manager"})})
    assert resp["statusCode"] == 404


def test_change_role_viewer_403(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5/role", "headers": _hdr("Viewer"),
                             "body": json.dumps({"role": "Manager"})})
    assert resp["statusCode"] == 403


# ---- delete ----

def test_delete_user_204(repo, bypass_user_check):
    repo.set("delete_user", {"id": 5})
    resp = function.handler({"httpMethod": "DELETE", "path": "/auth/users/5", "headers": _hdr("Admin")})
    assert resp["statusCode"] == 204 and resp["body"] == ""


def test_delete_self_400(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "DELETE", "path": "/auth/users/5", "headers": _hdr("Admin", sub="5")})
    assert resp["statusCode"] == 400
    assert "own account" in _body(resp)["error"]


def test_delete_user_not_found_404(repo, bypass_user_check):
    repo.set("delete_user", None)
    resp = function.handler({"httpMethod": "DELETE", "path": "/auth/users/999", "headers": _hdr("Admin")})
    assert resp["statusCode"] == 404


def test_delete_user_manager_403(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "DELETE", "path": "/auth/users/5", "headers": _hdr("Manager")})
    assert resp["statusCode"] == 403


def test_users_wrong_method_405(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "POST", "path": "/auth/users", "headers": _hdr("Admin")})
    assert resp["statusCode"] == 405


# ---- update details (username/email) ----

def test_update_user_details_200(repo, bypass_user_check):
    repo.set("update_user_details", {**A_USER, "username": "sam2", "email": "sam2@acme.test"})
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5", "headers": _hdr("Admin"),
                             "body": json.dumps({"username": "sam2", "email": "sam2@acme.test"})})
    assert resp["statusCode"] == 200
    body = _body(resp)
    assert body["username"] == "sam2" and body["email"] == "sam2@acme.test"
    assert repo.calls["update_user_details"]["kwargs"] == {"username": "sam2", "email": "sam2@acme.test"}


def test_update_user_duplicate_400(repo, bypass_user_check):
    repo.set("update_user_details", DuplicateUserError("sam2"))
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5", "headers": _hdr("Admin"),
                             "body": json.dumps({"username": "taken"})})
    assert resp["statusCode"] == 400
    assert "already in use" in _body(resp)["error"]


def test_update_user_invalid_email_400(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5", "headers": _hdr("Admin"),
                             "body": json.dumps({"email": "not-an-email"})})
    assert resp["statusCode"] == 400
    assert any("email" in d for d in _body(resp)["details"])


def test_update_user_empty_username_400(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5", "headers": _hdr("Admin"),
                             "body": json.dumps({"username": "   "})})
    assert resp["statusCode"] == 400


def test_update_user_not_found_404(repo, bypass_user_check):
    repo.set("update_user_details", None)
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/999", "headers": _hdr("Admin"),
                             "body": json.dumps({"username": "ok"})})
    assert resp["statusCode"] == 404


def test_update_user_viewer_403(repo, bypass_user_check):
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5", "headers": _hdr("Viewer"),
                             "body": json.dumps({"username": "ok"})})
    assert resp["statusCode"] == 403


def test_update_user_no_token_401(repo):
    resp = function.handler({"httpMethod": "PUT", "path": "/auth/users/5", "body": json.dumps({"username": "ok"})})
    assert resp["statusCode"] == 401
