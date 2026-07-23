"""
Tests for the activity log / audit trail.

Two layers:
  * Unit — the shared `activity` module (diff / actor / record-never-raises).
    This logic is identical in every service (synced from backend/_shared), so
    it is exercised once here.
  * Integration — driving the real projects handler against local PostgreSQL and
    asserting that create / update / delete each write the expected activity_log
    entry, including field-level changes on update.
"""

from datetime import date
from decimal import Decimal

import pytest

import activity
import auth
import postgres_service
import function


# ---------------------------------------------------------------------------
# Unit: activity.diff
# ---------------------------------------------------------------------------

def test_diff_reports_field_level_changes():
    before = {"id": 1, "name": "Apollo", "status": "planning", "budget_planned": Decimal("100.00")}
    after = {"id": 1, "name": "Apollo", "status": "active", "budget_planned": Decimal("100.00")}
    changes = activity.diff(before, after)
    assert changes == [{"field": "status", "old": "planning", "new": "active"}]


def test_diff_ignores_id_and_timestamps():
    before = {"id": 1, "created_at": "a", "updated_at": "b", "name": "X"}
    after = {"id": 1, "created_at": "c", "updated_at": "d", "name": "Y"}
    fields = [c["field"] for c in activity.diff(before, after)]
    assert fields == ["name"]  # id/created_at/updated_at never diffed


def test_diff_coerces_decimal_and_dates_to_json_safe():
    before = {"budget_planned": Decimal("1.50"), "deadline": date(2026, 1, 1)}
    after = {"budget_planned": Decimal("2.50"), "deadline": date(2026, 2, 2)}
    changes = {c["field"]: (c["old"], c["new"]) for c in activity.diff(before, after)}
    assert changes["budget_planned"] == (1.5, 2.5)              # Decimal -> float
    assert changes["deadline"] == ("2026-01-01", "2026-02-02")  # date -> ISO string


def test_diff_empty_when_nothing_changed():
    row = {"id": 1, "name": "Apollo", "status": "active"}
    assert activity.diff(row, dict(row)) == []


# ---------------------------------------------------------------------------
# Unit: activity.actor
# ---------------------------------------------------------------------------

def test_actor_extracts_id_and_username_from_bearer_token():
    token = auth.create_token({"sub": "42", "username": "lalitha", "role": "Admin"})
    got = activity.actor({"headers": {"Authorization": f"Bearer {token}"}})
    assert got == {"id": 42, "username": "lalitha"}


def test_actor_is_anonymous_without_a_token():
    assert activity.actor({"headers": {}}) == {"id": None, "username": None}
    assert activity.actor({}) == {"id": None, "username": None}


def test_actor_is_anonymous_on_a_garbage_token():
    assert activity.actor({"headers": {"Authorization": "Bearer not-a-jwt"}}) == {"id": None, "username": None}


# ---------------------------------------------------------------------------
# Unit: record() must NEVER raise (logging can't break the main operation)
# ---------------------------------------------------------------------------

def test_record_swallows_db_errors_and_returns_none(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db is on fire")
    monkeypatch.setattr(activity, "record", activity.record)  # ensure real fn
    monkeypatch.setattr("postgres_service.execute", boom)
    # Must not raise despite the insert blowing up.
    assert activity.record({"id": 1, "username": "x"}, "created", "project", 1, "X") is None


def test_record_swallows_when_actor_is_none(monkeypatch):
    captured = {}
    monkeypatch.setattr("postgres_service.execute", lambda sql, params, **k: captured.update(params=params))
    activity.record(None, "created", "project", 1, "X")
    # user_id / username fall back to None without raising.
    assert captured["params"][0] is None and captured["params"][1] is None


# ---------------------------------------------------------------------------
# Integration: create / update / delete write the expected entry
# ---------------------------------------------------------------------------

def _database_ready():
    try:
        postgres_service.execute("SELECT 1 FROM activity_log LIMIT 1", fetch="one")
        return True
    except Exception:
        postgres_service.PG_CONN = None
        return False


integration = pytest.mark.skipif(
    not _database_ready(),
    reason="local PostgreSQL with the activity_log schema is not available",
)


@pytest.fixture
def actor_user():
    """A real user row so the activity FK (user_id -> users.id) is satisfied, plus
    a bearer token identifying that user. Cleaned up afterwards."""
    row = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) "
        "VALUES (%s, %s, %s, (SELECT id FROM roles WHERE name='Admin')) RETURNING id",
        ("activity-it-actor", "activity-it-actor@example-test.invalid", "x"),
        fetch="one",
    )
    uid = row["id"]
    token = auth.create_token({"sub": str(uid), "username": "activity-it-actor", "role": "Admin"})
    yield {"id": uid, "token": token}
    postgres_service.execute("DELETE FROM users WHERE id = %s", (uid,))


def _event(method, path, token, body=None):
    import json
    evt = {"httpMethod": method, "path": path, "headers": {"Authorization": f"Bearer {token}"}}
    if body is not None:
        evt["body"] = json.dumps(body)
    return evt


def _latest(entity_id, action):
    return postgres_service.execute(
        "SELECT * FROM activity_log WHERE entity_type='project' AND entity_id=%s AND action=%s "
        "ORDER BY id DESC LIMIT 1",
        (entity_id, action), fetch="one",
    )


@integration
def test_create_update_delete_write_activity_entries(actor_user):
    token = actor_user["token"]

    # CREATE
    created = function.handler(_event("POST", "/projects", token,
                                      {"name": "Activity IT Project", "status": "planning"}))
    import json
    pid = json.loads(created["body"])["id"]
    try:
        row = _latest(pid, "created")
        assert row is not None
        assert row["user_id"] == actor_user["id"]
        assert row["username"] == "activity-it-actor"
        assert row["entity_name"] == "Activity IT Project"
        assert row["changes"] is None  # creates carry no field-level diff

        # UPDATE — field-level change captured
        function.handler(_event("PUT", f"/projects/{pid}", token, {"status": "active"}))
        upd = _latest(pid, "updated")
        assert upd is not None
        assert upd["changes"] == [{"field": "status", "old": "planning", "new": "active"}]

        # DELETE
        function.handler(_event("DELETE", f"/projects/{pid}", token))
        deleted = _latest(pid, "deleted")
        assert deleted is not None and deleted["entity_name"] == "Activity IT Project"
    finally:
        postgres_service.execute("DELETE FROM projects WHERE id = %s", (pid,))
        postgres_service.execute("DELETE FROM activity_log WHERE entity_id = %s AND entity_type='project'", (pid,))
