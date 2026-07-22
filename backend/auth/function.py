"""
Lambda handler for the auth service (registration, login, current user).

Routes API-Gateway-style HTTP requests and returns Lambda-proxy responses
({statusCode, headers, body}) with the status codes the workshop guide expects:
200 (login/me), 201 (register), 400 (validation/duplicate), 401 (bad or missing
credentials), 403 (role assignment denied), 404 (unknown route/user),
405 (method not allowed), 500 (unexpected error).

Routes:
    POST /auth/register   create a user (default role Viewer; elevated roles Admin-only)
    POST /auth/login      verify credentials, return a JWT
    GET  /auth/me         return the current user described by the bearer token
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
    DuplicateUserError,
)
from validation import validate_register, validate_login

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


def _get_action(event):
    """Return the trailing path segment (register / login / me), or None."""
    path_params = event.get("pathParameters") or {}
    if path_params.get("action"):
        return path_params["action"]
    path = event.get("path") or event.get("rawPath") or ""
    segments = [s for s in path.split("/") if s]
    if segments and segments[-1] != "auth":
        return segments[-1]
    return None


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
# Entry point
# ---------------------------------------------------------------------------

def handler(event=None, context=None):
    """Route an incoming auth request."""
    event = event or {}
    logger.debug("Received event: %s", event)

    try:
        method = _get_method(event)
        action = _get_action(event)

        if action == "register":
            if method != "POST":
                return _error(405, f"Method {method} not allowed on /auth/register.")
            return _handle_register(event)
        if action == "login":
            if method != "POST":
                return _error(405, f"Method {method} not allowed on /auth/login.")
            return _handle_login(event)
        if action == "me":
            if method != "GET":
                return _error(405, f"Method {method} not allowed on /auth/me.")
            return _handle_me(event)

        return _error(404, "Unknown auth route. Use /auth/register, /auth/login, or /auth/me.")
    except json.JSONDecodeError:
        return _error(400, "Request body is not valid JSON.")
    except Exception as e:
        logger.error("Handler error: %s", str(e))
        return _error(500, "Internal server error.", str(e))


# Main entry point for local testing.
if __name__ == "__main__":
    print(handler({"httpMethod": "GET", "path": "/auth/me"}))
