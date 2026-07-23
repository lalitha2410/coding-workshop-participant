"""
Integration: the deliverables handler writes activity_log entries for
create / update / delete (with field-level changes on update).

The shared logging module (backend/_shared/activity.py) is unit-tested in the
projects suite; here we confirm this service is wired to it correctly.
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
    """A real actor user + a parent project (deliverables need a project_id)."""
    uid = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) "
        "VALUES (%s,%s,%s,(SELECT id FROM roles WHERE name='Admin')) RETURNING id",
        ("deliv-act-actor", "deliv-act-actor@example-test.invalid", "x"), fetch="one")["id"]
    pid = postgres_service.execute(
        "INSERT INTO projects (name) VALUES (%s) RETURNING id", ("Deliv Act Parent",), fetch="one")["id"]
    token = auth.create_token({"sub": str(uid), "username": "deliv-act-actor", "role": "Admin"})
    yield {"uid": uid, "pid": pid, "token": token}
    postgres_service.execute("DELETE FROM projects WHERE id = %s", (pid,))  # cascades deliverables
    postgres_service.execute("DELETE FROM users WHERE id = %s", (uid,))


def _evt(method, path, token, body=None):
    e = {"httpMethod": method, "path": path, "headers": {"Authorization": f"Bearer {token}"}}
    if body is not None:
        e["body"] = json.dumps(body)
    return e


def _latest(entity_id, action):
    return postgres_service.execute(
        "SELECT * FROM activity_log WHERE entity_type='deliverable' AND entity_id=%s AND action=%s "
        "ORDER BY id DESC LIMIT 1", (entity_id, action), fetch="one")


def test_create_update_delete_write_activity(ctx):
    token = ctx["token"]
    created = function.handler(_evt("POST", "/deliverables", token,
                                    {"name": "Act Deliverable", "project_id": ctx["pid"], "status": "not_started"}))
    did = json.loads(created["body"])["id"]

    row = _latest(did, "created")
    assert row and row["user_id"] == ctx["uid"] and row["entity_name"] == "Act Deliverable"

    function.handler(_evt("PUT", f"/deliverables/{did}", token, {"status": "in_progress"}))
    upd = _latest(did, "updated")
    assert upd and {"field": "status", "old": "not_started", "new": "in_progress"} in upd["changes"]

    function.handler(_evt("DELETE", f"/deliverables/{did}", token))
    assert _latest(did, "deleted") is not None
