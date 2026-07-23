"""
Integration: the allocations handler writes activity_log entries for
create / update / delete (with field-level changes on update). Allocations have
no name of their own, so the entity_name is a readable 'Resource on Project'.
"""

import json

import pytest

import auth
import postgres_service
import function


def _database_ready():
    try:
        postgres_service.execute("SELECT 1 FROM activity_log LIMIT 1", fetch="one")
        return True
    except Exception:
        postgres_service.PG_CONN = None
        return False


pytestmark = pytest.mark.skipif(
    not _database_ready(),
    reason="local PostgreSQL with the activity_log schema is not available",
)


@pytest.fixture
def ctx():
    uid = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) "
        "VALUES (%s,%s,%s,(SELECT id FROM roles WHERE name='Admin')) RETURNING id",
        ("alloc-act-actor", "alloc-act-actor@example-test.invalid", "x"), fetch="one")["id"]
    rid = postgres_service.execute(
        "INSERT INTO resources (name, email) VALUES (%s,%s) RETURNING id",
        ("Alloc Act Resource", "alloc-act-res@example-test.invalid"), fetch="one")["id"]
    pid = postgres_service.execute(
        "INSERT INTO projects (name) VALUES (%s) RETURNING id", ("Alloc Act Project",), fetch="one")["id"]
    token = auth.create_token({"sub": str(uid), "username": "alloc-act-actor", "role": "Admin"})
    yield {"uid": uid, "rid": rid, "pid": pid, "token": token}
    postgres_service.execute("DELETE FROM projects WHERE id = %s", (pid,))   # cascades allocations
    postgres_service.execute("DELETE FROM resources WHERE id = %s", (rid,))
    postgres_service.execute("DELETE FROM users WHERE id = %s", (uid,))


def _evt(method, path, token, body=None):
    e = {"httpMethod": method, "path": path, "headers": {"Authorization": f"Bearer {token}"}}
    if body is not None:
        e["body"] = json.dumps(body)
    return e


def _latest(entity_id, action):
    return postgres_service.execute(
        "SELECT * FROM activity_log WHERE entity_type='allocation' AND entity_id=%s AND action=%s "
        "ORDER BY id DESC LIMIT 1", (entity_id, action), fetch="one")


def test_create_update_delete_write_activity(ctx):
    token = ctx["token"]
    created = function.handler(_evt("POST", "/allocations", token,
                                    {"resource_id": ctx["rid"], "project_id": ctx["pid"], "allocation_pct": 40}))
    aid = json.loads(created["body"])["id"]

    row = _latest(aid, "created")
    assert row and row["user_id"] == ctx["uid"]
    # name-less entity -> readable 'Resource on Project' label
    assert row["entity_name"] == "Alloc Act Resource on Alloc Act Project"

    function.handler(_evt("PUT", f"/allocations/{aid}", token, {"allocation_pct": 75}))
    upd = _latest(aid, "updated")
    assert upd and {"field": "allocation_pct", "old": 40, "new": 75} in upd["changes"]

    function.handler(_evt("DELETE", f"/allocations/{aid}", token))
    assert _latest(aid, "deleted") is not None
