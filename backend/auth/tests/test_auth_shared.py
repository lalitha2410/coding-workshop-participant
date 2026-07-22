"""Unit tests for the shared auth module (passwords, JWT, RBAC) — no database."""

import time

import jwt
import pytest

import auth


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

def _event_with_token(token):
    return {"headers": {"Authorization": f"Bearer {token}"}}


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
