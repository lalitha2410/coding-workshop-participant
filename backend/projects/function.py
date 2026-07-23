"""
Lambda handler for the projects CRUD service.

Routes API-Gateway-style HTTP requests to the projects repository and returns
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
import activity
from projects_repository import (
    list_projects,
    get_project,
    create_project,
    update_project,
    delete_project,
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


def _get_path_id(event):
    """Extract the {id} path segment from pathParameters or the raw path."""
    path_params = event.get("pathParameters") or {}
    if path_params.get("id"):
        return path_params["id"]
    path = event.get("path") or event.get("rawPath") or ""
    segments = [s for s in path.split("/") if s]
    if segments and segments[-1] != "projects":
        return segments[-1]
    return None


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
    result = list_projects(
        status=query.get("status"),
        department=query.get("department"),
        limit=limit,
        offset=offset,
    )
    return _response(200, result)


def _handle_get(project_id):
    pid = _parse_id(project_id)
    if pid is None:
        return _error(404, f"Project '{project_id}' not found.")
    project = get_project(pid)
    if project is None:
        return _error(404, f"Project {pid} not found.")
    return _response(200, project)


def _handle_create(event):
    data = _get_body(event)
    errors = validate_create(data)
    if errors:
        return _error(400, "Validation failed.", errors)
    project = create_project(data)
    activity.record(activity.actor(event), "created", "project", project["id"], project["name"])
    return _response(201, project)


def _handle_update(project_id, event):
    pid = _parse_id(project_id)
    if pid is None:
        return _error(404, f"Project '{project_id}' not found.")
    data = _get_body(event)
    errors = validate_update(data)
    if errors:
        return _error(400, "Validation failed.", errors)
    before = get_project(pid)
    if before is None:
        return _error(404, f"Project {pid} not found.")
    project = update_project(pid, data)
    if project is None:
        return _error(404, f"Project {pid} not found.")
    changes = activity.diff(before, project)
    if changes:
        activity.record(activity.actor(event), "updated", "project", project["id"], project["name"], changes)
    return _response(200, project)


def _handle_delete(project_id, event):
    pid = _parse_id(project_id)
    if pid is None:
        return _error(404, f"Project '{project_id}' not found.")
    deleted = delete_project(pid)
    if deleted is None:
        return _error(404, f"Project {pid} not found.")
    activity.record(activity.actor(event), "deleted", "project", deleted["id"], deleted["name"])
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
        # 401 if unauthenticated / user deleted; 403 if role unknown or lacks permission.
        auth.authorize_request(event, method, user_exists=auth.db_user_exists)
        project_id = _get_path_id(event)

        if method == "GET":
            return _handle_get(project_id) if project_id else _handle_list(event)
        if method == "POST":
            return _handle_create(event)
        if method == "PUT":
            if not project_id:
                return _error(400, "A project id is required to update.")
            return _handle_update(project_id, event)
        if method == "DELETE":
            if not project_id:
                return _error(400, "A project id is required to delete.")
            return _handle_delete(project_id, event)

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
    print(handler({"httpMethod": "GET", "path": "/projects"}))
