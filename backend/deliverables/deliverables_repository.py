"""
Data-access layer for the `deliverables` table.

Each function is a thin, parameterized SQL wrapper over postgres_service.execute
and returns plain dicts (rows) so the handler layer stays free of DB concerns.
"""

import psycopg

from postgres_service import execute

# Business columns returned to API clients (id + all deliverable fields).
_COLUMNS = (
    "id, project_id, name, description, status, completion_pct, "
    "due_date, created_at, updated_at"
)

# Compact projection for dependency views (the linked deliverables).
_DEP_COLUMNS = "id, project_id, name, status, completion_pct, due_date"


class DuplicateDependencyError(Exception):
    """Raised when a (deliverable_id, depends_on_id) dependency already exists."""


def _deliverable_filters(project_id, status, search=None):
    """Build the shared WHERE clause + params for list/count."""
    clauses, params = [], []
    if project_id:
        clauses.append("project_id = %s")
        params.append(project_id)
    if status:
        clauses.append("status = %s")
        params.append(status)
    if search:
        # Case-insensitive partial match on name or description. Parameterized.
        clauses.append("(name ILIKE %s OR description ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def list_deliverables(project_id=None, status=None, search=None, limit=50, offset=0):
    """
    Return a page of deliverables (optionally filtered) plus pagination info.

    Shape: {"items": [...], "total": <int>, "limit": <int>, "offset": <int>}.
    `total` counts all rows matching the filters, ignoring limit/offset.
    """
    where, params = _deliverable_filters(project_id, status, search)
    total = execute(f"SELECT COUNT(*) AS n FROM deliverables{where}", params, fetch="one")["n"]
    items = execute(
        f"SELECT {_COLUMNS} FROM deliverables{where} ORDER BY id LIMIT %s OFFSET %s",
        params + [limit, offset],
        fetch="all",
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


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
    sql = "DELETE FROM deliverables WHERE id = %s RETURNING id, name"
    return execute(sql, (deliverable_id,), fetch="one")


def project_exists(project_id):
    """Return True if a project with the given id exists (FK reference check)."""
    row = execute("SELECT 1 FROM projects WHERE id = %s", (project_id,), fetch="one")
    return row is not None


# ---------------------------------------------------------------------------
# Dependencies (deliverable_dependencies join table)
#   row (deliverable_id=X, depends_on_id=Y)  ==  "X depends on Y"
# ---------------------------------------------------------------------------

def deliverable_exists(deliverable_id):
    """Return True if a deliverable with the given id exists."""
    row = execute("SELECT 1 FROM deliverables WHERE id = %s", (deliverable_id,), fetch="one")
    return row is not None


def add_dependency(deliverable_id, depends_on_id):
    """Insert a dependency edge (deliverable_id depends on depends_on_id).

    Raises DuplicateDependencyError if the edge already exists.
    """
    sql = "INSERT INTO deliverable_dependencies (deliverable_id, depends_on_id) VALUES (%s, %s)"
    try:
        execute(sql, (deliverable_id, depends_on_id))
    except psycopg.errors.UniqueViolation:
        raise DuplicateDependencyError((deliverable_id, depends_on_id))
    return {"deliverable_id": deliverable_id, "depends_on_id": depends_on_id}


def remove_dependency(deliverable_id, depends_on_id):
    """Delete a dependency edge; return the removed pair or None if it didn't exist."""
    sql = (
        "DELETE FROM deliverable_dependencies WHERE deliverable_id = %s AND depends_on_id = %s "
        "RETURNING deliverable_id, depends_on_id"
    )
    return execute(sql, (deliverable_id, depends_on_id), fetch="one")


def get_dependencies(deliverable_id):
    """Return the deliverables that `deliverable_id` depends on."""
    sql = f"""
        SELECT {', '.join('d.' + c for c in _DEP_COLUMNS.split(', '))}
        FROM deliverable_dependencies dd
        JOIN deliverables d ON d.id = dd.depends_on_id
        WHERE dd.deliverable_id = %s
        ORDER BY d.id
    """
    return execute(sql, (deliverable_id,), fetch="all")


def get_dependents(deliverable_id):
    """Return the deliverables that depend on `deliverable_id`."""
    sql = f"""
        SELECT {', '.join('d.' + c for c in _DEP_COLUMNS.split(', '))}
        FROM deliverable_dependencies dd
        JOIN deliverables d ON d.id = dd.deliverable_id
        WHERE dd.depends_on_id = %s
        ORDER BY d.id
    """
    return execute(sql, (deliverable_id,), fetch="all")


# Hard cap on traversal depth — a last-resort guard against pathological data.
_MAX_DEPTH = 10000


def path_exists(from_id, to_id):
    """
    True if `from_id` transitively depends on `to_id` (follows depends-on edges).

    Used for cycle prevention: before adding A -> B, reject if path_exists(B, A),
    i.e. B already reaches A directly or transitively.

    The recursive CTE carries a **visited path** and never re-enters a node already
    on that path, and a **depth cap** as a second guard — so it terminates even if
    the table somehow already contained a cycle (e.g. inserted out-of-band),
    rather than looping forever.
    """
    sql = """
        WITH RECURSIVE deps(id, depth, path) AS (
            SELECT depends_on_id, 1, ARRAY[deliverable_id, depends_on_id]
            FROM deliverable_dependencies
            WHERE deliverable_id = %s
          UNION ALL
            SELECT dd.depends_on_id, d.depth + 1, d.path || dd.depends_on_id
            FROM deliverable_dependencies dd
            JOIN deps d ON dd.deliverable_id = d.id
            WHERE dd.depends_on_id <> ALL(d.path)   -- visited-set: never revisit a node
              AND d.depth < %s                       -- depth cap: belt-and-suspenders
        )
        SELECT 1 FROM deps WHERE id = %s LIMIT 1
    """
    return execute(sql, (from_id, _MAX_DEPTH, to_id), fetch="one") is not None
