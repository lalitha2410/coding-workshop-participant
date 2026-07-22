"""
Data-access layer for the `allocations` table (resources <-> projects join).

Each function is a thin, parameterized SQL wrapper over postgres_service.execute
and returns plain dicts (rows) so the handler layer stays free of DB concerns.

The (resource_id, project_id) pair is UNIQUE; create/update translate the
database UniqueViolation into a DuplicateAllocationError so the handler can
return a clean 400. Foreign keys to resources/projects are pre-checked by the
handler (resource_exists / project_exists) for friendly messages.
"""

import psycopg

from postgres_service import execute


class DuplicateAllocationError(Exception):
    """Raised when a (resource_id, project_id) pair already exists."""

    def __init__(self, resource_id, project_id):
        self.resource_id = resource_id
        self.project_id = project_id
        super().__init__(
            f"resource {resource_id} is already allocated to project {project_id}"
        )


# Business columns (the allocations table has no created_at/updated_at).
_COLUMNS = "id, resource_id, project_id, allocation_pct, start_date, end_date"


def list_allocations(resource_id=None, project_id=None):
    """Return all allocations, optionally filtered by resource_id and/or project_id."""
    sql = f"SELECT {_COLUMNS} FROM allocations"
    clauses = []
    params = []
    if resource_id:
        clauses.append("resource_id = %s")
        params.append(resource_id)
    if project_id:
        clauses.append("project_id = %s")
        params.append(project_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    return execute(sql, params, fetch="all")


def get_allocation(allocation_id):
    """Return a single allocation by id, or None if it does not exist."""
    sql = f"SELECT {_COLUMNS} FROM allocations WHERE id = %s"
    return execute(sql, (allocation_id,), fetch="one")


def create_allocation(data):
    """Insert a new allocation and return the created row.

    Raises DuplicateAllocationError if the (resource_id, project_id) pair exists.
    """
    sql = f"""
        INSERT INTO allocations (resource_id, project_id, allocation_pct, start_date, end_date)
        VALUES (%s, %s, COALESCE(%s, 0), %s, %s)
        RETURNING {_COLUMNS}
    """
    params = (
        data.get("resource_id"),
        data.get("project_id"),
        data.get("allocation_pct"),
        data.get("start_date"),
        data.get("end_date"),
    )
    try:
        return execute(sql, params, fetch="one")
    except psycopg.errors.UniqueViolation:
        raise DuplicateAllocationError(data.get("resource_id"), data.get("project_id"))


def update_allocation(allocation_id, data):
    """
    Partially update an allocation and return the updated row (None if not found).

    COALESCE keeps the existing column value whenever the incoming field is None.
    (The allocations table has no updated_at column, so none is set here.)

    Raises DuplicateAllocationError if the change collides with an existing
    (resource_id, project_id) pair.
    """
    sql = f"""
        UPDATE allocations SET
            resource_id    = COALESCE(%s, resource_id),
            project_id     = COALESCE(%s, project_id),
            allocation_pct = COALESCE(%s, allocation_pct),
            start_date     = COALESCE(%s, start_date),
            end_date       = COALESCE(%s, end_date)
        WHERE id = %s
        RETURNING {_COLUMNS}
    """
    params = (
        data.get("resource_id"),
        data.get("project_id"),
        data.get("allocation_pct"),
        data.get("start_date"),
        data.get("end_date"),
        allocation_id,
    )
    try:
        return execute(sql, params, fetch="one")
    except psycopg.errors.UniqueViolation:
        raise DuplicateAllocationError(data.get("resource_id"), data.get("project_id"))


def delete_allocation(allocation_id):
    """Delete an allocation; return the deleted row ({"id": ...}) or None if not found."""
    sql = "DELETE FROM allocations WHERE id = %s RETURNING id"
    return execute(sql, (allocation_id,), fetch="one")


def resource_exists(resource_id):
    """Return True if a resource with the given id exists (FK reference check)."""
    row = execute("SELECT 1 FROM resources WHERE id = %s", (resource_id,), fetch="one")
    return row is not None


def project_exists(project_id):
    """Return True if a project with the given id exists (FK reference check)."""
    row = execute("SELECT 1 FROM projects WHERE id = %s", (project_id,), fetch="one")
    return row is not None


def resource_allocation_totals(over_only=False):
    """
    Sum each resource's allocation percentage across all of its projects.

    Each row is:
        {resource_id, resource_name, email, total_allocation_pct,
         project_count, over_allocated}
    where over_allocated is True when the summed percentage exceeds 100.

    over_only=False (summary): LEFT JOIN, so EVERY resource is listed, including
        those with no allocations (total 0, over_allocated False) — useful for
        spotting underutilized/available people.
    over_only=True (over-allocated): INNER JOIN + HAVING > 100, so only resources
        that are actually over-allocated appear. Answers the workshop question
        "which team members are over-allocated across projects".
    """
    join = "JOIN" if over_only else "LEFT JOIN"
    having = "HAVING COALESCE(SUM(a.allocation_pct), 0) > 100" if over_only else ""
    sql = f"""
        SELECT r.id                             AS resource_id,
               r.name                           AS resource_name,
               r.email                          AS email,
               COALESCE(SUM(a.allocation_pct), 0) AS total_allocation_pct,
               COUNT(a.id)                      AS project_count
        FROM resources r
        {join} allocations a ON a.resource_id = r.id
        GROUP BY r.id, r.name, r.email
        {having}
        ORDER BY total_allocation_pct DESC, r.id
    """
    rows = execute(sql, fetch="all")
    for row in rows:
        row["over_allocated"] = row["total_allocation_pct"] > 100
    return rows
