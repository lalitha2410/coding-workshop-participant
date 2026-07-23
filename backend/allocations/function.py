"""
Lambda handler for the allocations CRUD service (resources <-> projects join).

Routes API-Gateway-style HTTP requests to the allocations repository and returns
Lambda-proxy responses ({statusCode, headers, body}) with the status codes the
workshop guide expects: 200 (read/update), 201 (create), 204 (delete),
400 (validation/bad request/missing reference/duplicate), 404 (not found),
405 (method not allowed), 500 (unexpected error).

Analytics routes (GET):
    /allocations/over-allocated  -> resources whose summed allocation > 100%
    /allocations/summary         -> per-resource allocation totals + flag
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal

import auth
import activity
from allocations_repository import (
    list_allocations,
    get_allocation,
    create_allocation,
    update_allocation,
    delete_allocation,
    resource_exists,
    project_exists,
    resource_allocation_totals,
    allocation_label,
    DuplicateAllocationError,
)
from validation import validate_create, validate_update
from pagination import parse_pagination, parse_search, PaginationError

# Configure logging for Lambda.
logger = logging.getLogger()
logger.setLevel(logging.INFO)

JSON_HEADERS = {"Content-Type": "application/json"}

# GET sub-resources that are analytics views rather than an allocation id.
_SUMMARY_ACTIONS = {"over-allocated", "summary"}


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
    if segments and segments[-1] != "allocations":
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


def _missing_references(data):
    """Return a list like ['resource 5', 'project 9'] for references that don't exist.

    Only checks ids that are present (non-None), so it is safe for partial updates.
    """
    missing = []
    resource_id = data.get("resource_id")
    project_id = data.get("project_id")
    if resource_id is not None and not resource_exists(resource_id):
        missing.append(f"resource {resource_id}")
    if project_id is not None and not project_exists(project_id):
        missing.append(f"project {project_id}")
    return missing


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _handle_list(event):
    query = _get_query(event)
    try:
        limit, offset = parse_pagination(query)
        search = parse_search(query)
    except PaginationError as exc:
        return _error(400, str(exc))
    result = list_allocations(
        resource_id=query.get("resource_id"),
        project_id=query.get("project_id"),
        search=search,
        limit=limit,
        offset=offset,
    )
    return _response(200, result)


def _handle_summary(over_only):
    return _response(200, resource_allocation_totals(over_only=over_only))


def _handle_get(allocation_id):
    aid = _parse_id(allocation_id)
    if aid is None:
        return _error(404, f"Allocation '{allocation_id}' not found.")
    allocation = get_allocation(aid)
    if allocation is None:
        return _error(404, f"Allocation {aid} not found.")
    return _response(200, allocation)


def _handle_create(event):
    data = _get_body(event)
    errors = validate_create(data)
    if errors:
        return _error(400, "Validation failed.", errors)
    # Dual foreign-key reference check.
    missing = _missing_references(data)
    if missing:
        return _error(400, f"Referenced {' and '.join(missing)} does not exist.")
    try:
        allocation = create_allocation(data)
    except DuplicateAllocationError as dup:
        return _error(
            400,
            f"Resource {dup.resource_id} is already allocated to project {dup.project_id}.",
        )
    label = allocation_label(allocation["resource_id"], allocation["project_id"])
    activity.record(activity.actor(event), "created", "allocation", allocation["id"], label)
    return _response(201, allocation)


def _handle_update(allocation_id, event):
    aid = _parse_id(allocation_id)
    if aid is None:
        return _error(404, f"Allocation '{allocation_id}' not found.")
    data = _get_body(event)
    errors = validate_update(data)
    if errors:
        return _error(400, "Validation failed.", errors)
    missing = _missing_references(data)
    if missing:
        return _error(400, f"Referenced {' and '.join(missing)} does not exist.")
    before = get_allocation(aid)
    if before is None:
        return _error(404, f"Allocation {aid} not found.")
    try:
        allocation = update_allocation(aid, data)
    except DuplicateAllocationError as dup:
        return _error(
            400,
            f"Resource {dup.resource_id} is already allocated to project {dup.project_id}.",
        )
    if allocation is None:
        return _error(404, f"Allocation {aid} not found.")
    changes = activity.diff(before, allocation)
    if changes:
        label = allocation_label(allocation["resource_id"], allocation["project_id"])
        activity.record(activity.actor(event), "updated", "allocation", allocation["id"], label, changes)
    return _response(200, allocation)


def _handle_delete(allocation_id, event):
    aid = _parse_id(allocation_id)
    if aid is None:
        return _error(404, f"Allocation '{allocation_id}' not found.")
    deleted = delete_allocation(aid)
    if deleted is None:
        return _error(404, f"Allocation {aid} not found.")
    label = allocation_label(deleted["resource_id"], deleted["project_id"])
    activity.record(activity.actor(event), "deleted", "allocation", deleted["id"], label)
    return _no_content()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def handler(event=None, context=None):
    """Route an incoming request to the matching CRUD or analytics operation."""
    event = event or {}
    logger.debug("Received event: %s", event)

    try:
        method = _get_method(event)
        # 401 if unauthenticated / user deleted; 403 if role unknown or lacks permission.
        auth.authorize_request(event, method, user_exists=auth.db_user_exists)
        allocation_id = _get_path_id(event)

        if method == "GET":
            if allocation_id == "over-allocated":
                return _handle_summary(over_only=True)
            if allocation_id == "summary":
                return _handle_summary(over_only=False)
            if allocation_id:
                return _handle_get(allocation_id)
            return _handle_list(event)
        if method == "POST":
            return _handle_create(event)
        if method == "PUT":
            if not allocation_id or allocation_id in _SUMMARY_ACTIONS:
                return _error(400, "An allocation id is required to update.")
            return _handle_update(allocation_id, event)
        if method == "DELETE":
            if not allocation_id or allocation_id in _SUMMARY_ACTIONS:
                return _error(400, "An allocation id is required to delete.")
            return _handle_delete(allocation_id, event)

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
    print(handler({"httpMethod": "GET", "path": "/allocations"}))
