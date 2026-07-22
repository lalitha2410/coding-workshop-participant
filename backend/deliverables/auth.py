# ============================================================
# GENERATED FILE - DO NOT EDIT
# Source of truth: backend/_shared/auth.py
# Regenerate with: bin/sync-shared.sh
# ============================================================
"""
Shared authentication & RBAC helpers for backend services.

Canonical source of truth. This module is propagated into each backend service
folder by bin/sync-shared.sh so every Lambda bundles its own copy. Edit this
file — never the generated copies under backend/<service>/auth.py.

Stateless (no database access): passwords are hashed with bcrypt, sessions are
carried as HS256 JWTs. Services call:

    from auth import authenticate, require_permission, AuthError

    def handler(event, context):
        try:
            principal = authenticate(event)          # 401 if no/invalid token
            require_permission(principal, "delete")   # 403 if role lacks it
        except AuthError as err:
            return err.response
        ...

Environment:
    JWT_SECRET       signing secret (local default provided; override in cloud)
    JWT_EXPIRES_MIN  token lifetime in minutes (default 60)
"""

import json
import os
import time

import bcrypt
import jwt

JSON_HEADERS = {"Content-Type": "application/json"}

# --- RBAC model ------------------------------------------------------------

READ = "read"
CREATE = "create"
UPDATE = "update"
DELETE = "delete"
MANAGE_USERS = "manage_users"

# Role -> set of permitted actions (the workshop's access matrix).
ROLE_PERMISSIONS = {
    "Viewer": {READ},
    "Contributor": {READ, CREATE, UPDATE},
    "Manager": {READ, CREATE, UPDATE, DELETE},
    "Admin": {READ, CREATE, UPDATE, DELETE, MANAGE_USERS},
}

# The only roles the system recognizes. A validly-signed token carrying anything
# else is treated as invalid (fail-safe -> Forbidden), never granted access.
VALID_ROLES = frozenset(ROLE_PERMISSIONS)


# --- Errors ----------------------------------------------------------------

class AuthError(Exception):
    """Base class for auth failures; carries an HTTP status code."""

    status_code = 400

    @property
    def response(self):
        """Render as a standard Lambda-proxy error response."""
        return {
            "statusCode": self.status_code,
            "headers": JSON_HEADERS,
            "body": json.dumps({"error": str(self)}),
        }


class Unauthorized(AuthError):
    """401 — authentication is missing or invalid."""

    status_code = 401


class Forbidden(AuthError):
    """403 — authenticated but not permitted."""

    status_code = 403


# --- Configuration ---------------------------------------------------------

def _secret():
    return os.getenv("JWT_SECRET", "local-dev-jwt-secret-change-me")


def token_ttl_seconds():
    """Token lifetime in seconds, from JWT_EXPIRES_MIN (default 60 minutes)."""
    try:
        minutes = int(os.getenv("JWT_EXPIRES_MIN", "60"))
    except (TypeError, ValueError):
        minutes = 60
    return minutes * 60


# --- Passwords -------------------------------------------------------------

def hash_password(plain):
    """Hash a plaintext password with bcrypt; returns a text hash for storage."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain, hashed):
    """Return True if `plain` matches the stored bcrypt hash; False otherwise."""
    if not isinstance(plain, str) or not isinstance(hashed, str):
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed stored hash -> treat as a non-match rather than crashing.
        return False


# --- JWT -------------------------------------------------------------------

def create_token(claims, expires_in=None):
    """Create a signed HS256 JWT from `claims` plus iat/exp."""
    now = int(time.time())
    ttl = token_ttl_seconds() if expires_in is None else expires_in
    payload = {**claims, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_token(token):
    """Decode/verify a JWT; raises jwt exceptions on invalid/expired tokens."""
    return jwt.decode(token, _secret(), algorithms=["HS256"])


# --- Middleware / authorization -------------------------------------------

def _bearer_token(event):
    """Extract the bearer token from the event; raises Unauthorized if absent/malformed."""
    headers = event.get("headers") or {}
    value = None
    for key, val in headers.items():
        if isinstance(key, str) and key.lower() == "authorization":
            value = val
            break
    if not value:
        raise Unauthorized("Missing Authorization header.")
    parts = value.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise Unauthorized("Authorization header must be in the form 'Bearer <token>'.")
    return parts[1]


def authenticate(event, user_exists=None):
    """
    Validate the request's bearer token and return its claims (the principal).

    Claims include: sub (user id, as a string), username, role, iat, exp.

    Fail-safe checks after the signature is verified:
      * the `role` claim must be one of VALID_ROLES, else Forbidden (403);
      * if a `user_exists` callable is supplied, the subject must still exist,
        else Unauthorized (401).

    Raises Unauthorized (401) for missing/malformed/invalid/expired tokens or a
    subject that no longer exists; Forbidden (403) for an unrecognized role.
    Never fails open.
    """
    token = _bearer_token(event)
    try:
        claims = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Authentication token has expired.")
    except jwt.InvalidTokenError:
        raise Unauthorized("Invalid authentication token.")

    # Reject tokens whose role is not one the system recognizes.
    if claims.get("role") not in VALID_ROLES:
        raise Forbidden(f"Access denied: unrecognized role '{claims.get('role')}'.")

    # Reject tokens whose subject no longer exists (deleted/revoked user).
    if user_exists is not None:
        try:
            user_id = int(claims.get("sub"))
        except (TypeError, ValueError):
            raise Unauthorized("Invalid authentication token subject.")
        if not user_exists(user_id):
            raise Unauthorized("Authenticated user no longer exists.")

    return claims


def role_can(role, action):
    """Return True if `role` is permitted to perform `action`."""
    return action in ROLE_PERMISSIONS.get(role, set())


def require_role(principal, *roles):
    """Raise Forbidden unless the principal's role is one of `roles`."""
    if not principal or principal.get("role") not in roles:
        raise Forbidden("Access denied: insufficient role.")


def require_permission(principal, action):
    """Raise Forbidden unless the principal's role permits `action`."""
    role = (principal or {}).get("role")
    if not role_can(role, action):
        raise Forbidden(f"Access denied: '{role}' cannot {action}.")


# HTTP method -> required RBAC action. Methods not listed (e.g. PATCH) require
# authentication only; routing then decides the outcome (e.g. 405).
METHOD_PERMISSIONS = {
    "GET": READ,
    "POST": CREATE,
    "PUT": UPDATE,
    "DELETE": DELETE,
}


def authorize_request(event, method=None, user_exists=None):
    """
    Gate a request: authenticate it (optionally checking the subject still
    exists via `user_exists`), then enforce the RBAC permission for its HTTP
    method. Returns the principal (claims).

    Raises Unauthorized (401) when the bearer token is missing/invalid/expired
    or the user no longer exists, or Forbidden (403) when the role is unknown or
    lacks the permission the method requires (GET->read, POST->create,
    PUT->update, DELETE->delete). Methods without a mapped action require only
    authentication.
    """
    principal = authenticate(event, user_exists=user_exists)
    action = METHOD_PERMISSIONS.get((method or "GET").upper())
    if action is not None:
        require_permission(principal, action)
    return principal


def db_user_exists(user_id):
    """
    Return True if a user row with this id exists.

    Requires postgres_service (bundled alongside this module in every service).
    Services pass this as the `user_exists` callback so a deleted/revoked user is
    rejected with 401 even while their JWT is otherwise still valid.
    """
    from postgres_service import execute
    return execute("SELECT 1 FROM users WHERE id = %s", (user_id,), fetch="one") is not None
