"""
Tests for GET /auth/activity — the audit-trail read endpoint and its RBAC.

RBAC rules under test (all enforced in the BACKEND, not just the UI):
  * Viewer / Contributor            -> 403 (no view_activity permission)
  * Manager                         -> 200, but entity_type='user' entries hidden
  * Admin                           -> 200, sees everything including user actions

Layers:
  * Unit — handler enforcement with list_activity mocked (fast, deterministic).
  * Integration — real PostgreSQL: repository filtering, newest-first ordering,
    pagination, and user-management CRUD writing 'user' entries with field diffs.
"""

import json

import pytest

import auth
import function
import postgres_service
from activity_repository import list_activity


def _hdr(role, sub="1"):
    token = auth.create_token({"sub": sub, "username": "u", "role": role})
    return {"Authorization": f"Bearer {token}"}


def _get(path, headers, query=None):
    evt = {"httpMethod": "GET", "path": path, "headers": headers}
    if query:
        evt["queryStringParameters"] = query
    return function.handler(evt)


@pytest.fixture
def present_user(monkeypatch):
    """Treat the token subject as an existing user (the gate checks the DB)."""
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: True)


# ---------------------------------------------------------------------------
# Unit: handler-level RBAC enforcement (list_activity mocked)
# ---------------------------------------------------------------------------

@pytest.fixture
def spy_list(monkeypatch):
    """Replace list_activity with a spy that records its kwargs."""
    calls = {}

    def _fake(**kwargs):
        calls.update(kwargs)
        return {"items": [], "total": 0, "limit": kwargs["limit"], "offset": kwargs["offset"]}

    monkeypatch.setattr(function, "list_activity", _fake)
    return calls


@pytest.mark.parametrize("role", ["Viewer", "Contributor"])
def test_viewer_and_contributor_get_403(present_user, spy_list, role):
    resp = _get("/auth/activity", _hdr(role))
    assert resp["statusCode"] == 403


def test_manager_is_allowed_but_hides_user_entities(present_user, spy_list):
    resp = _get("/auth/activity", _hdr("Manager"))
    assert resp["statusCode"] == 200
    # The Manager-vs-Admin rule is pushed into the query, not the UI.
    assert spy_list["include_user_entities"] is False


def test_admin_sees_everything(present_user, spy_list):
    resp = _get("/auth/activity", _hdr("Admin"))
    assert resp["statusCode"] == 200
    assert spy_list["include_user_entities"] is True


def test_filters_are_passed_through(present_user, spy_list):
    _get("/auth/activity", _hdr("Admin"),
         query={"entity_type": "project", "action": "updated", "user": "7"})
    assert spy_list["entity_type"] == "project"
    assert spy_list["action"] == "updated"
    assert spy_list["user_id"] == 7


def test_activity_requires_authentication():
    # No headers at all -> the auth gate rejects before RBAC.
    resp = function.handler({"httpMethod": "GET", "path": "/auth/activity", "headers": {}})
    assert resp["statusCode"] in (401, 403)


def test_activity_rejects_non_get():
    resp = function.handler({"httpMethod": "POST", "path": "/auth/activity", "headers": _hdr("Admin")})
    assert resp["statusCode"] == 405


# ---------------------------------------------------------------------------
# Integration: repository filtering / ordering / pagination
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

_TAG = "actrbac"  # unique entity_name marker so the tests only see their own rows


def _seed(action, entity_type, entity_name):
    postgres_service.execute(
        "INSERT INTO activity_log (username, action, entity_type, entity_id, entity_name) "
        "VALUES (%s, %s, %s, %s, %s)",
        ("seed", action, entity_type, 1, entity_name),
    )


@pytest.fixture
def seeded_rows():
    postgres_service.execute("DELETE FROM activity_log WHERE entity_name LIKE %s", (f"{_TAG}%",))
    _seed("created", "project", f"{_TAG}-proj")
    _seed("updated", "resource", f"{_TAG}-res")
    _seed("deleted", "user", f"{_TAG}-user")
    yield
    postgres_service.execute("DELETE FROM activity_log WHERE entity_name LIKE %s", (f"{_TAG}%",))


def _mine(result):
    return [r for r in result["items"] if (r["entity_name"] or "").startswith(_TAG)]


@integration
def test_manager_query_excludes_user_entities(seeded_rows):
    mgr = _mine(list_activity(include_user_entities=False, limit=500))
    types = {r["entity_type"] for r in mgr}
    assert "user" not in types           # hidden from Managers
    assert {"project", "resource"} <= types


@integration
def test_admin_query_includes_user_entities(seeded_rows):
    adm = _mine(list_activity(include_user_entities=True, limit=500))
    types = {r["entity_type"] for r in adm}
    assert "user" in types               # visible to Admins


@integration
def test_list_is_newest_first(seeded_rows):
    rows = _mine(list_activity(include_user_entities=True, limit=500))
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids, reverse=True)   # created_at DESC, id DESC


@integration
def test_filters_by_entity_type_and_action(seeded_rows):
    only_proj = _mine(list_activity(entity_type="project", include_user_entities=True, limit=500))
    assert only_proj and all(r["entity_type"] == "project" for r in only_proj)


@integration
def test_pagination_shape(seeded_rows):
    page = list_activity(include_user_entities=True, limit=2, offset=0)
    assert set(page) == {"items", "total", "limit", "offset"}
    assert page["limit"] == 2 and page["offset"] == 0 and len(page["items"]) <= 2


# ---------------------------------------------------------------------------
# Integration: user-management CRUD writes 'user' activity entries end-to-end,
# and Manager-vs-Admin visibility holds through the real handler.
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_admin():
    for u in ("actrbac-admin", "actrbac-mgr", "actrbac-target", "actrbac-renamed"):
        postgres_service.execute("DELETE FROM users WHERE username = %s", (u,))
    admin_role = postgres_service.execute("SELECT id FROM roles WHERE name='Admin'", fetch="one")["id"]
    mgr_role = postgres_service.execute("SELECT id FROM roles WHERE name='Manager'", fetch="one")["id"]
    aid = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) VALUES (%s,%s,%s,%s) RETURNING id",
        ("actrbac-admin", "actrbac-admin@example-test.invalid", auth.hash_password("adminpass123"), admin_role),
        fetch="one")["id"]
    mid = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) VALUES (%s,%s,%s,%s) RETURNING id",
        ("actrbac-mgr", "actrbac-mgr@example-test.invalid", auth.hash_password("mgrpass1234"), mgr_role),
        fetch="one")["id"]
    yield {"admin_id": aid, "mgr_id": mid}
    for u in ("actrbac-admin", "actrbac-mgr", "actrbac-target", "actrbac-renamed"):
        postgres_service.execute("DELETE FROM users WHERE username = %s", (u,))
    postgres_service.execute("DELETE FROM activity_log WHERE entity_name IN ('actrbac-target','actrbac-renamed')")


@integration
def test_user_crud_writes_entries_and_respects_visibility(seeded_admin):
    admin_tok = auth.create_token({"sub": str(seeded_admin["admin_id"]), "username": "actrbac-admin", "role": "Admin"})
    mgr_tok = auth.create_token({"sub": str(seeded_admin["mgr_id"]), "username": "actrbac-mgr", "role": "Manager"})
    admin_h = {"Authorization": f"Bearer {admin_tok}"}

    # CREATE a user (Admin) -> 'user' created entry
    created = function.handler({"httpMethod": "POST", "path": "/auth/register", "headers": admin_h,
                                "body": json.dumps({"username": "actrbac-target",
                                                    "email": "actrbac-target@example-test.invalid",
                                                    "password": "password123", "role": "Viewer"})})
    target_id = json.loads(created["body"])["id"]

    # UPDATE the user's username -> field-level change captured
    function.handler({"httpMethod": "PUT", "path": f"/auth/users/{target_id}", "headers": admin_h,
                      "body": json.dumps({"username": "actrbac-renamed",
                                          "email": "actrbac-target@example-test.invalid"})})
    upd = postgres_service.execute(
        "SELECT changes FROM activity_log WHERE entity_type='user' AND entity_id=%s AND action='updated' "
        "ORDER BY id DESC LIMIT 1", (target_id,), fetch="one")
    assert upd is not None
    assert {"field": "username", "old": "actrbac-target", "new": "actrbac-renamed"} in upd["changes"]

    # The Admin sees this user entry via the endpoint...
    admin_view = _get("/auth/activity", admin_h, query={"entity_type": "user"})
    admin_ids = [e["entity_id"] for e in json.loads(admin_view["body"])["items"]]
    assert target_id in admin_ids

    # ...the Manager must NOT (user entries are Admin-only). The Manager is a real
    # user row, so the auth gate's db_user_exists check passes for their token.
    mgr_view = function.handler({"httpMethod": "GET", "path": "/auth/activity",
                                 "headers": {"Authorization": f"Bearer {mgr_tok}"}})
    assert mgr_view["statusCode"] == 200
    mgr_types = {e["entity_type"] for e in json.loads(mgr_view["body"])["items"]}
    assert "user" not in mgr_types

    # DELETE the user (Admin) -> 'user' deleted entry, history keeps the name
    function.handler({"httpMethod": "DELETE", "path": f"/auth/users/{target_id}", "headers": admin_h})
    deleted = postgres_service.execute(
        "SELECT entity_name FROM activity_log WHERE entity_type='user' AND entity_id=%s AND action='deleted' "
        "ORDER BY id DESC LIMIT 1", (target_id,), fetch="one")
    assert deleted is not None and deleted["entity_name"] == "actrbac-renamed"
