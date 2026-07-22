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

from deliverables_repository import (
    list_deliverables,
    get_deliverable,
    create_deliverable,
    update_deliverable,
    delete_deliverable,
    project_exists,
)
from validation import validate_create, validate_update

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
    if segments and segments[-1] != "deliverables":
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
    deliverables = list_deliverables(
        project_id=query.get("project_id"),
        status=query.get("status"),
    )
    return _response(200, deliverables)


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
# Entry point
# ---------------------------------------------------------------------------

def handler(event=None, context=None):
    """Route an incoming request to the matching CRUD operation."""
    event = event or {}
    logger.debug("Received event: %s", event)

    try:
        method = _get_method(event)
        deliverable_id = _get_path_id(event)

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
    except json.JSONDecodeError:
        return _error(400, "Request body is not valid JSON.")
    except Exception as e:
        logger.error("Handler error: %s", str(e))
        return _error(500, "Internal server error.", str(e))


# Main entry point for local testing.
if __name__ == "__main__":
    print(handler({"httpMethod": "GET", "path": "/deliverables"}))
