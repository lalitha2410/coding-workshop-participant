"""
Lambda handler for the deliverables CRUD service.

Routes API-Gateway-style HTTP requests to the deliverables repository and returns
Lambda-proxy responses ({statusCode, headers, body}) with the status codes the
workshop guide expects: 200 (read/update), 201 (create), 204 (delete),
400 (validation/bad request), 404 (not found), 405 (method not allowed),
500 (unexpected error).
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal

import auth
from deliverables_repository import (
    list_deliverables,
    get_deliverable,
    create_deliverable,
    update_deliverable,
    delete_deliverable,
    project_exists,
    deliverable_exists,
    add_dependency,
    remove_dependency,
    get_dependencies,
    get_dependents,
    path_exists,
    DuplicateDependencyError,
)
from validation import validate_create, validate_update
from pagination import parse_pagination, PaginationError

# Configure logging for Lambda.
logger = logging.getLogger()
logger.setLevel(logging.INFO)

JSON_HEADERS = {"Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _json_default(value):
    """Serialize DB types (date/datetime/Decimal) that json.dumps can't handle."""
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


def _no_content():
    # 204 responses carry no body.
    return {"statusCode": 204, "headers": JSON_HEADERS, "body": ""}


# ---------------------------------------------------------------------------
# Event parsing (tolerant of API Gateway v1 and v2 shapes)
# ---------------------------------------------------------------------------

def _get_method(event):
    method = event.get("httpMethod")
    if not method:
        method = event.get("requestContext", {}).get("http", {}).get("method")
    return (method or "GET").upper()


def _parse_path(event):
    """
    Return the path segments after 'deliverables'. Examples:
      /deliverables                       -> []
      /deliverables/5                     -> ['5']
      /deliverables/5/dependencies        -> ['5', 'dependencies']
      /deliverables/5/dependencies/3      -> ['5', 'dependencies', '3']
    """
    path = event.get("path") or event.get("rawPath") or ""
    segments = [s for s in path.split("/") if s]
    if "deliverables" in segments:
        idx = segments.index("deliverables")
        return segments[idx + 1:]
    return segments


def _parse_id(raw):
    """Return the id as an int, or None if it is missing/non-numeric."""
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _get_query(event):
    return event.get("queryStringParameters") or {}


def _get_body(event):
    """Parse the JSON request body; raises json.JSONDecodeError on malformed input."""
    raw = event.get("body")
    if raw is None or raw == "":
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _handle_list(event):
    query = _get_query(event)
    try:
        limit, offset = parse_pagination(query)
    except PaginationError as exc:
        return _error(400, str(exc))
    result = list_deliverables(
        project_id=query.get("project_id"),
        status=query.get("status"),
        limit=limit,
        offset=offset,
    )
    return _response(200, result)


def _handle_get(deliverable_id):
    did = _parse_id(deliverable_id)
    if did is None:
        return _error(404, f"Deliverable '{deliverable_id}' not found.")
    deliverable = get_deliverable(did)
    if deliverable is None:
        return _error(404, f"Deliverable {did} not found.")
    return _response(200, deliverable)


def _handle_create(event):
    data = _get_body(event)
    errors = validate_create(data)
    if errors:
        return _error(400, "Validation failed.", errors)
    # Cross-entity reference check: the parent project must exist.
    if not project_exists(data.get("project_id")):
        return _error(400, f"Referenced project {data.get('project_id')} does not exist.")
    deliverable = create_deliverable(data)
    return _response(201, deliverable)


def _handle_update(deliverable_id, event):
    did = _parse_id(deliverable_id)
    if did is None:
        return _error(404, f"Deliverable '{deliverable_id}' not found.")
    data = _get_body(event)
    errors = validate_update(data)
    if errors:
        return _error(400, "Validation failed.", errors)
    # If the project_id is being changed, the new parent project must exist.
    if data.get("project_id") is not None and not project_exists(data.get("project_id")):
        return _error(400, f"Referenced project {data.get('project_id')} does not exist.")
    deliverable = update_deliverable(did, data)
    if deliverable is None:
        return _error(404, f"Deliverable {did} not found.")
    return _response(200, deliverable)


def _handle_delete(deliverable_id):
    did = _parse_id(deliverable_id)
    if did is None:
        return _error(404, f"Deliverable '{deliverable_id}' not found.")
    deleted = delete_deliverable(did)
    if deleted is None:
        return _error(404, f"Deliverable {did} not found.")
    return _no_content()


# ---------------------------------------------------------------------------
# Dependency route handlers  (/deliverables/{id}/dependencies[/{depends_on_id}])
# ---------------------------------------------------------------------------

def _handle_get_dependencies(deliverable_id):
    did = _parse_id(deliverable_id)
    if did is None or not deliverable_exists(did):
        return _error(404, f"Deliverable {deliverable_id} not found.")
    return _response(200, {
        "deliverable_id": did,
        "depends_on": get_dependencies(did),   # what this deliverable depends on
        "dependents": get_dependents(did),     # what depends on this deliverable
    })


def _handle_add_dependency(deliverable_id, event):
    did = _parse_id(deliverable_id)
    if did is None or not deliverable_exists(did):
        return _error(404, f"Deliverable {deliverable_id} not found.")

    data = _get_body(event)
    dep_on = data.get("depends_on_id")
    if not isinstance(dep_on, int) or isinstance(dep_on, bool):
        try:
            dep_on = int(dep_on)
        except (TypeError, ValueError):
            return _error(400, "`depends_on_id` is required and must be an integer.")

    if dep_on == did:
        return _error(400, "A deliverable cannot depend on itself.")
    if not deliverable_exists(dep_on):
        return _error(400, f"Referenced deliverable {dep_on} does not exist.")
    # Cycle check: adding did -> dep_on is a cycle if dep_on already reaches did.
    if path_exists(dep_on, did):
        return _error(400, f"Adding this dependency would create a cycle (deliverable {dep_on} already depends on {did}).")

    try:
        edge = add_dependency(did, dep_on)
    except DuplicateDependencyError:
        return _error(400, f"Deliverable {did} already depends on {dep_on}.")
    return _response(201, edge)


def _handle_remove_dependency(deliverable_id, depends_on_id):
    did = _parse_id(deliverable_id)
    dep_on = _parse_id(depends_on_id)
    if did is None or dep_on is None:
        return _error(404, "Dependency not found.")
    removed = remove_dependency(did, dep_on)
    if removed is None:
        return _error(404, f"Deliverable {did} does not depend on {dep_on}.")
    return _no_content()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def handler(event=None, context=None):
    """Route an incoming request to the matching CRUD operation."""
    event = event or {}
    logger.debug("Received event: %s", event)

    try:
        method = _get_method(event)
        segments = _parse_path(event)
        is_dependency = len(segments) >= 2 and segments[1] == "dependencies"

        # Authenticate first (401 for missing/invalid/expired/deleted-user; 403 for
        # unknown role), then enforce the permission this specific route needs.
        principal = auth.authenticate(event, user_exists=auth.db_user_exists)
        if is_dependency:
            # Reads are open to any role; adding/removing a dependency is Contributor+
            # (mapped to the create permission — NOT delete, so remove isn't Manager-only).
            if method in ("POST", "DELETE"):
                auth.require_permission(principal, auth.CREATE)
        else:
            action = auth.METHOD_PERMISSIONS.get(method)
            if action is not None:
                auth.require_permission(principal, action)

        deliverable_id = segments[0] if segments else None

        # --- Dependency sub-resource routes ---
        if is_dependency:
            if method == "GET" and len(segments) == 2:
                return _handle_get_dependencies(deliverable_id)
            if method == "POST" and len(segments) == 2:
                return _handle_add_dependency(deliverable_id, event)
            if method == "DELETE" and len(segments) == 3:
                return _handle_remove_dependency(deliverable_id, segments[2])
            return _error(405, f"Method {method} not allowed on this path.")

        # --- Deliverable CRUD routes ---
        if method == "GET":
            return _handle_get(deliverable_id) if deliverable_id else _handle_list(event)
        if method == "POST":
            return _handle_create(event)
        if method == "PUT":
            if not deliverable_id:
                return _error(400, "A deliverable id is required to update.")
            return _handle_update(deliverable_id, event)
        if method == "DELETE":
            if not deliverable_id:
                return _error(400, "A deliverable id is required to delete.")
            return _handle_delete(deliverable_id)

        return _error(405, f"Method {method} not allowed.")
    except auth.AuthError as err:
        return err.response
    except json.JSONDecodeError:
        return _error(400, "Request body is not valid JSON.")
    except Exception as e:
        logger.error("Handler error: %s", str(e))
        return _error(500, "Internal server error.", str(e))


# Main entry point for local testing.
if __name__ == "__main__":
    print(handler({"httpMethod": "GET", "path": "/deliverables"}))
