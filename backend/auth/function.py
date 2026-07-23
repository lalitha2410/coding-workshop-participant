"""
Lambda handler for the auth service (registration, login, current user).

Routes API-Gateway-style HTTP requests and returns Lambda-proxy responses
({statusCode, headers, body}) with the status codes the workshop guide expects:
200 (login/me), 201 (register), 400 (validation/duplicate), 401 (bad or missing
credentials), 403 (role assignment denied), 404 (unknown route/user),
405 (method not allowed), 500 (unexpected error).

Routes:
    POST   /auth/register        create a user (default role Viewer; elevated roles Admin-only)
    POST   /auth/login           verify credentials, return a JWT
    GET    /auth/me              return the current user described by the bearer token
    GET    /auth/users           list users (Admin only; paginated, optional ?search)
    PUT    /auth/users/{id}/role change a user's role (Admin only)
    DELETE /auth/users/{id}      delete a user (Admin only)
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal

import auth
from users_repository import (
    get_user_by_id,
    get_user_for_login,
    create_user,
    get_role_by_name,
    list_users,
    update_user_role,
    update_user_details,
    delete_user,
    DuplicateUserError,
)
from validation import validate_register, validate_login, validate_user_update
from pagination import parse_pagination, PaginationError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

JSON_HEADERS = {"Content-Type": "application/json"}

# New users self-register as Viewer; any other role requires an Admin caller.
DEFAULT_ROLE = "Viewer"


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS,
        "body": json.dumps(body, default=_json_default),
    }


def _error(status_code, message, details=None):
    payload = {"error": message}
    if details is not None:
        payload["details"] = details
    return _response(status_code, payload)


# ---------------------------------------------------------------------------
# Event parsing
# ---------------------------------------------------------------------------

def _get_method(event):
    method = event.get("httpMethod")
    if not method:
        method = event.get("requestContext", {}).get("http", {}).get("method")
    return (method or "GET").upper()


def _parse_path(event):
    """
    Return path segments after 'auth'. Examples:
      /auth/login                 -> ['login']
      /auth/users                 -> ['users']
      /auth/users/5               -> ['users', '5']
      /auth/users/5/role          -> ['users', '5', 'role']
    """
    path = event.get("path") or event.get("rawPath") or ""
    segments = [s for s in path.split("/") if s]
    if "auth" in segments:
        idx = segments.index("auth")
        return segments[idx + 1:]
    return segments


def _parse_id(raw):
    """Return the id as an int, or None if it is missing/non-numeric."""
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _no_content():
    return {"statusCode": 204, "headers": JSON_HEADERS, "body": ""}


def _get_body(event):
    raw = event.get("body")
    if raw is None or raw == "":
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    return json.loads(raw)


def _public_user(row, keys=("id", "username", "email", "role")):
    return {k: row[k] for k in keys if k in row}


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _handle_register(event):
    data = _get_body(event)
    errors = validate_register(data)
    if errors:
        return _error(400, "Validation failed.", errors)

    role_name = data.get("role") or DEFAULT_ROLE
    # Assigning any non-default role requires an authenticated Admin.
    if role_name != DEFAULT_ROLE:
        try:
            principal = auth.authenticate(event)
        except auth.AuthError:
            return _error(403, f"Access denied: only an Admin can assign the '{role_name}' role.")
        if principal.get("role") != "Admin":
            return _error(403, f"Access denied: only an Admin can assign the '{role_name}' role.")

    role = get_role_by_name(role_name)
    if role is None:
        return _error(400, f"Unknown role '{role_name}'.")

    password_hash = auth.hash_password(data["password"])
    try:
        user = create_user(data["username"], data["email"], password_hash, role["id"])
    except DuplicateUserError:
        return _error(400, "Username or email is already in use.")
    return _response(201, user)


def _handle_login(event):
    data = _get_body(event)
    errors = validate_login(data)
    if errors:
        return _error(400, "Validation failed.", errors)

    identifier = data.get("username") or data.get("email")
    user = get_user_for_login(identifier)
    # Same message whether the user is unknown or the password is wrong.
    if user is None or not auth.verify_password(data["password"], user["password_hash"]):
        return _error(401, "Invalid credentials.")

    token = auth.create_token({
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user["role"],
    })
    return _response(200, {
        "token": token,
        "token_type": "Bearer",
        "expires_in": auth.token_ttl_seconds(),
        "user": _public_user(user),
    })


def _handle_me(event):
    try:
        principal = auth.authenticate(event)
    except auth.AuthError as err:
        return err.response
    user = get_user_by_id(int(principal["sub"]))
    if user is None:
        # Validly-signed token, but the subject no longer exists -> fail safe.
        return _error(401, "Authenticated user no longer exists.")
    return _response(200, user)


# ---------------------------------------------------------------------------
# Admin user management  (/auth/users[...])
# ---------------------------------------------------------------------------

def _require_admin(event):
    """Authenticate and require the manage_users permission (Admin). Raises AuthError."""
    principal = auth.authenticate(event, user_exists=auth.db_user_exists)
    auth.require_permission(principal, auth.MANAGE_USERS)
    return principal


def _handle_list_users(event):
    _require_admin(event)
    query = event.get("queryStringParameters") or {}
    try:
        limit, offset = parse_pagination(query)
    except PaginationError as exc:
        return _error(400, str(exc))
    return _response(200, list_users(search=query.get("search"), limit=limit, offset=offset))


def _handle_change_role(event, user_id):
    principal = _require_admin(event)
    uid = _parse_id(user_id)
    if uid is None:
        return _error(404, f"User '{user_id}' not found.")

    data = _get_body(event)
    role_name = data.get("role")
    if role_name not in auth.VALID_ROLES:
        return _error(400, f"`role` must be one of: {', '.join(sorted(auth.VALID_ROLES))}.")

    # Guard: an admin must not demote themselves out of Admin (would lock them out).
    if uid == int(principal["sub"]) and role_name != "Admin":
        return _error(400, "You can't change your own role away from Admin.")

    role = get_role_by_name(role_name)
    if role is None:
        return _error(400, f"Unknown role '{role_name}'.")
    updated = update_user_role(uid, role["id"])
    if updated is None:
        return _error(404, f"User {uid} not found.")
    return _response(200, updated)


def _handle_update_user(event, user_id):
    """Admin: update a user's username/email (not password, not role)."""
    _require_admin(event)
    uid = _parse_id(user_id)
    if uid is None:
        return _error(404, f"User '{user_id}' not found.")

    data = _get_body(event)
    errors = validate_user_update(data)
    if errors:
        return _error(400, "Validation failed.", errors)
    try:
        updated = update_user_details(uid, username=data.get("username"), email=data.get("email"))
    except DuplicateUserError:
        return _error(400, "Username or email is already in use.")
    if updated is None:
        return _error(404, f"User {uid} not found.")
    return _response(200, updated)


def _handle_delete_user(event, user_id):
    principal = _require_admin(event)
    uid = _parse_id(user_id)
    if uid is None:
        return _error(404, f"User '{user_id}' not found.")

    # Guard: an admin must not delete their own account.
    if uid == int(principal["sub"]):
        return _error(400, "You can't delete your own account.")

    deleted = delete_user(uid)
    if deleted is None:
        return _error(404, f"User {uid} not found.")
    return _no_content()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def handler(event=None, context=None):
    """Route an incoming auth request."""
    event = event or {}
    logger.debug("Received event: %s", event)

    try:
        method = _get_method(event)
        segments = _parse_path(event)
        action = segments[0] if segments else None

        if action == "register" and len(segments) == 1:
            if method != "POST":
                return _error(405, f"Method {method} not allowed on /auth/register.")
            return _handle_register(event)
        if action == "login" and len(segments) == 1:
            if method != "POST":
                return _error(405, f"Method {method} not allowed on /auth/login.")
            return _handle_login(event)
        if action == "me" and len(segments) == 1:
            if method != "GET":
                return _error(405, f"Method {method} not allowed on /auth/me.")
            return _handle_me(event)

        # --- Admin user management ---
        if action == "users":
            if method == "GET" and len(segments) == 1:
                return _handle_list_users(event)
            if method == "PUT" and len(segments) == 3 and segments[2] == "role":
                return _handle_change_role(event, segments[1])
            if method == "PUT" and len(segments) == 2:
                return _handle_update_user(event, segments[1])
            if method == "DELETE" and len(segments) == 2:
                return _handle_delete_user(event, segments[1])
            return _error(405, f"Method {method} not allowed on this /auth/users path.")

        return _error(404, "Unknown auth route.")
    except auth.AuthError as err:
        return err.response
    except json.JSONDecodeError:
        return _error(400, "Request body is not valid JSON.")
    except Exception as e:
        logger.error("Handler error: %s", str(e))
        return _error(500, "Internal server error.", str(e))


# Main entry point for local testing.
if __name__ == "__main__":
    print(handler({"httpMethod": "GET", "path": "/auth/me"}))
