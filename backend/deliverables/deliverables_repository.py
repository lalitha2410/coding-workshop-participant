"""
Data-access layer for the `deliverables` table.

Each function is a thin, parameterized SQL wrapper over postgres_service.execute
and returns plain dicts (rows) so the handler layer stays free of DB concerns.
"""

from postgres_service import execute

# Business columns returned to API clients (id + all deliverable fields).
_COLUMNS = (
    "id, project_id, name, description, status, completion_pct, "
    "due_date, created_at, updated_at"
)


def list_deliverables(project_id=None, status=None):
    """Return all deliverables, optionally filtered by project_id and/or status."""
    sql = f"SELECT {_COLUMNS} FROM deliverables"
    clauses = []
    params = []
    if project_id:
        clauses.append("project_id = %s")
        params.append(project_id)
    if status:
        clauses.append("status = %s")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    return execute(sql, params, fetch="all")


def get_deliverable(deliverable_id):
    """Return a single deliverable by id, or None if it does not exist."""
    sql = f"SELECT {_COLUMNS} FROM deliverables WHERE id = %s"
    return execute(sql, (deliverable_id,), fetch="one")


def create_deliverable(data):
    """Insert a new deliverable and return the created row."""
    sql = f"""
        INSERT INTO deliverables
            (project_id, name, description, status, completion_pct, due_date)
        VALUES
            (%s, %s, %s, COALESCE(%s, 'not_started'), COALESCE(%s, 0), %s)
        RETURNING {_COLUMNS}
    """
    params = (
        data.get("project_id"),
        data.get("name"),
        data.get("description"),
        data.get("status"),
        data.get("completion_pct"),
        data.get("due_date"),
    )
    return execute(sql, params, fetch="one")


def update_deliverable(deliverable_id, data):
    """
    Partially update a deliverable and return the updated row (None if not found).

    COALESCE keeps the existing column value whenever the incoming field is None,
    so callers only need to send the fields they want to change. updated_at is set
    explicitly to NOW() on every update.
    """
    sql = f"""
        UPDATE deliverables SET
            project_id     = COALESCE(%s, project_id),
            name           = COALESCE(%s, name),
            description    = COALESCE(%s, description),
            status         = COALESCE(%s, status),
            completion_pct = COALESCE(%s, completion_pct),
            due_date       = COALESCE(%s, due_date),
            updated_at     = NOW()
        WHERE id = %s
        RETURNING {_COLUMNS}
    """
    params = (
        data.get("project_id"),
        data.get("name"),
        data.get("description"),
        data.get("status"),
        data.get("completion_pct"),
        data.get("due_date"),
        deliverable_id,
    )
    return execute(sql, params, fetch="one")


def delete_deliverable(deliverable_id):
    """Delete a deliverable; return the deleted row ({"id": ...}) or None if not found."""
    sql = "DELETE FROM deliverables WHERE id = %s RETURNING id"
    return execute(sql, (deliverable_id,), fetch="one")


def project_exists(project_id):
    """Return True if a project with the given id exists (FK reference check)."""
    row = execute("SELECT 1 FROM projects WHERE id = %s", (project_id,), fetch="one")
    return row is not None
