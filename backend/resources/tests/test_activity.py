"""
Integration: the resources handler writes activity_log entries for
create / update / delete (with field-level changes on update).
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
def actor():
    uid = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) "
        "VALUES (%s,%s,%s,(SELECT id FROM roles WHERE name='Admin')) RETURNING id",
        ("res-act-actor", "res-act-actor@example-test.invalid", "x"), fetch="one")["id"]
    token = auth.create_token({"sub": str(uid), "username": "res-act-actor", "role": "Admin"})
    yield {"uid": uid, "token": token}
    postgres_service.execute("DELETE FROM users WHERE id = %s", (uid,))


def _evt(method, path, token, body=None):
    e = {"httpMethod": method, "path": path, "headers": {"Authorization": f"Bearer {token}"}}
    if body is not None:
        e["body"] = json.dumps(body)
    return e


def _latest(entity_id, action):
    return postgres_service.execute(
        "SELECT * FROM activity_log WHERE entity_type='resource' AND entity_id=%s AND action=%s "
        "ORDER BY id DESC LIMIT 1", (entity_id, action), fetch="one")


def test_create_update_delete_write_activity(actor):
    token = actor["token"]
    created = function.handler(_evt("POST", "/resources", token,
                                    {"name": "Act Resource", "email": "act-res@example-test.invalid",
                                     "title": "Engineer"}))
    rid = json.loads(created["body"])["id"]
    try:
        row = _latest(rid, "created")
        assert row and row["user_id"] == actor["uid"] and row["entity_name"] == "Act Resource"

        function.handler(_evt("PUT", f"/resources/{rid}", token, {"title": "Staff Engineer"}))
        upd = _latest(rid, "updated")
        assert upd and {"field": "title", "old": "Engineer", "new": "Staff Engineer"} in upd["changes"]

        function.handler(_evt("DELETE", f"/resources/{rid}", token))
        assert _latest(rid, "deleted") is not None
    finally:
        postgres_service.execute("DELETE FROM resources WHERE id = %s", (rid,))
        postgres_service.execute("DELETE FROM activity_log WHERE entity_type='resource' AND entity_id=%s", (rid,))
