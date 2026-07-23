"""
Data-access layer for the `projects` table.

Each function is a thin, parameterized SQL wrapper over postgres_service.execute
and returns plain dicts (rows) so the handler layer stays free of DB concerns.
"""

from postgres_service import execute

# Business columns returned to API clients (id + all project fields).
_COLUMNS = (
    "id, name, description, status, department, "
    "start_date, end_date, deadline, budget_planned, budget_consumed, "
    "created_at, updated_at"
)


def _project_filters(status, department, search=None):
    """Build the shared WHERE clause + params for list/count."""
    clauses, params = [], []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if department:
        clauses.append("department = %s")
        params.append(department)
    if search:
        # Case-insensitive partial match on name or description. Parameterized.
        clauses.append("(name ILIKE %s OR description ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_projects(status=None, department=None, search=None, limit=50, offset=0):
    """
    Return a page of projects (optionally filtered) plus pagination info.

    Shape: {"items": [...], "total": <int>, "limit": <int>, "offset": <int>}.
    `total` counts all rows matching the filters, ignoring limit/offset.
    """
    where, params = _project_filters(status, department, search)
    total = execute(f"SELECT COUNT(*) AS n FROM projects{where}", params, fetch="one")["n"]
    items = execute(
        f"SELECT {_COLUMNS} FROM projects{where} ORDER BY id LIMIT %s OFFSET %s",
        params + [limit, offset],
        fetch="all",
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_project(project_id):
    """Return a single project by id, or None if it does not exist."""
    sql = f"SELECT {_COLUMNS} FROM projects WHERE id = %s"
    return execute(sql, (project_id,), fetch="one")


def create_project(data):
    """Insert a new project and return the created row."""
    sql = f"""
        INSERT INTO projects
            (name, description, status, department,
             start_date, end_date, deadline, budget_planned, budget_consumed)
        VALUES
            (%s, %s, COALESCE(%s, 'planning'), %s,
             %s, %s, %s, COALESCE(%s, 0), COALESCE(%s, 0))
        RETURNING {_COLUMNS}
    """
    params = (
        data.get("name"),
        data.get("description"),
        data.get("status"),
        data.get("department"),
        data.get("start_date"),
        data.get("end_date"),
        data.get("deadline"),
        data.get("budget_planned"),
        data.get("budget_consumed"),
    )
    return execute(sql, params, fetch="one")


def update_project(project_id, data):
    """
    Partially update a project and return the updated row (None if not found).

    COALESCE keeps the existing column value whenever the incoming field is None,
    so callers only need to send the fields they want to change. updated_at is set
    explicitly to NOW() on every update.
    """
    sql = f"""
        UPDATE projects SET
            name            = COALESCE(%s, name),
            description     = COALESCE(%s, description),
            status          = COALESCE(%s, status),
            department      = COALESCE(%s, department),
            start_date      = COALESCE(%s, start_date),
            end_date        = COALESCE(%s, end_date),
            deadline        = COALESCE(%s, deadline),
            budget_planned  = COALESCE(%s, budget_planned),
            budget_consumed = COALESCE(%s, budget_consumed),
            updated_at      = NOW()
        WHERE id = %s
        RETURNING {_COLUMNS}
    """
    params = (
        data.get("name"),
        data.get("description"),
        data.get("status"),
        data.get("department"),
        data.get("start_date"),
        data.get("end_date"),
        data.get("deadline"),
        data.get("budget_planned"),
        data.get("budget_consumed"),
        project_id,
    )
    return execute(sql, params, fetch="one")


def delete_project(project_id):
    """Delete a project; return the deleted row ({"id": ...}) or None if not found."""
    sql = "DELETE FROM projects WHERE id = %s RETURNING id, name"
    return execute(sql, (project_id,), fetch="one")
