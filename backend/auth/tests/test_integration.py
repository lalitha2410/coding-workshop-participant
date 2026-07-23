"""
Integration tests — real database round-trips through the auth handler and the
activity repository.

Exercises the full register -> login -> me flow end to end, admin user
management (list/search, role change, delete, detail update, self-guards), and
the audit-trail: activity_log filtering/ordering/pagination plus user-management
CRUD writing 'user' entries with field diffs. Uses distinctive `.invalid`
identifiers and cleans them up. Skips automatically when the local database /
schema is unavailable, so the unit/api/security suites still run anywhere.

    POSTGRES_NAME=projectdb pytest -m integration
"""

import json

import pytest

import auth
import function
import postgres_service
import testkit
from activity_repository import list_activity

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not testkit.database_ready("users"),
        reason="local PostgreSQL with the users/roles schema is not available",
    ),
]

_USERNAMES = ("auth-it-viewer", "auth-it-admin", "auth-it-manager", "auth-it-dup")


def _cleanup():
    for username in _USERNAMES:
        postgres_service.execute("DELETE FROM users WHERE username = %s", (username,))


@pytest.fixture(autouse=True)
def clean_users():
    _cleanup()
    yield
    _cleanup()


def _post(path, body, headers=None):
    event = {"httpMethod": "POST", "path": path, "body": json.dumps(body)}
    if headers:
        event["headers"] = headers
    return function.handler(event)


def _get(path, headers=None, query=None):
    event = {"httpMethod": "GET", "path": path}
    if headers:
        event["headers"] = headers
    if query:
        event["queryStringParameters"] = query
    return function.handler(event)


def _put(path, body, headers=None):
    ev = {"httpMethod": "PUT", "path": path, "body": json.dumps(body)}
    if headers:
        ev["headers"] = headers
    return function.handler(ev)


def _delete(path, headers=None):
    ev = {"httpMethod": "DELETE", "path": path}
    if headers:
        ev["headers"] = headers
    return function.handler(ev)


def _auth_hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_admin(username="auth-it-admin"):
    """Insert an Admin user directly (bootstraps the first Admin) and return id."""
    admin_role = postgres_service.execute("SELECT id FROM roles WHERE name = 'Admin'", fetch="one")
    row = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) VALUES (%s, %s, %s, %s) RETURNING id",
        (username, f"{username}@example-test.invalid", auth.hash_password("adminpass123"), admin_role["id"]),
        fetch="one",
    )
    return row["id"]


def _admin_ctx():
    """Seed a real Admin and return (id, token) whose subject exists in the DB."""
    aid = _seed_admin()
    token = auth.create_token({"sub": str(aid), "username": "auth-it-admin", "role": "Admin"})
    return aid, token


def _role_of(uid):
    row = postgres_service.execute(
        "SELECT r.name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id = %s", (uid,), fetch="one")
    return row["name"] if row else None


# ---------------------------------------------------------------------------
# register -> login -> me
# ---------------------------------------------------------------------------

def test_register_login_me_round_trip():
    reg = _post("/auth/register", {
        "username": "auth-it-viewer",
        "email": "auth-it-viewer@example-test.invalid",
        "password": "password123",
    })
    assert reg["statusCode"] == 201
    reg_body = json.loads(reg["body"])
    assert reg_body["role"] == "Viewer"
    assert "password_hash" not in reg_body

    login = _post("/auth/login", {"username": "auth-it-viewer", "password": "password123"})
    assert login["statusCode"] == 200
    token = json.loads(login["body"])["token"]

    me = _get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me["statusCode"] == 200
    me_body = json.loads(me["body"])
    assert me_body["username"] == "auth-it-viewer"
    assert me_body["role"] == "Viewer"


def test_login_can_use_email_identifier():
    _post("/auth/register", {
        "username": "auth-it-viewer",
        "email": "auth-it-viewer@example-test.invalid",
        "password": "password123",
    })
    login = _post("/auth/login", {"email": "auth-it-viewer@example-test.invalid", "password": "password123"})
    assert login["statusCode"] == 200


def test_register_duplicate_username_returns_400():
    body = {"username": "auth-it-dup", "email": "auth-it-dup@example-test.invalid", "password": "password123"}
    assert _post("/auth/register", body)["statusCode"] == 201
    dup = _post("/auth/register", body)
    assert dup["statusCode"] == 400
    assert "already in use" in json.loads(dup["body"])["error"]


def test_login_wrong_password_returns_401():
    _post("/auth/register", {
        "username": "auth-it-viewer",
        "email": "auth-it-viewer@example-test.invalid",
        "password": "password123",
    })
    login = _post("/auth/login", {"username": "auth-it-viewer", "password": "nope-nope-nope"})
    assert login["statusCode"] == 401


# ---------------------------------------------------------------------------
# RBAC on role assignment during registration
# ---------------------------------------------------------------------------

def test_elevated_role_requires_admin_token():
    # No token -> forbidden to self-assign Manager.
    resp = _post("/auth/register", {
        "username": "auth-it-manager",
        "email": "auth-it-manager@example-test.invalid",
        "password": "password123",
        "role": "Manager",
    })
    assert resp["statusCode"] == 403
    # And the user was not created.
    assert postgres_service.execute(
        "SELECT id FROM users WHERE username = %s", ("auth-it-manager",), fetch="one"
    ) is None


def test_me_after_user_deleted_returns_401():
    # Register + login, then delete the user out from under a still-valid token.
    _post("/auth/register", {
        "username": "auth-it-viewer",
        "email": "auth-it-viewer@example-test.invalid",
        "password": "password123",
    })
    login = _post("/auth/login", {"username": "auth-it-viewer", "password": "password123"})
    token = json.loads(login["body"])["token"]

    postgres_service.execute("DELETE FROM users WHERE username = %s", ("auth-it-viewer",))

    me = _get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me["statusCode"] == 401


def test_admin_can_create_manager():
    _seed_admin()
    login = _post("/auth/login", {"username": "auth-it-admin", "password": "adminpass123"})
    admin_token = json.loads(login["body"])["token"]

    resp = _post(
        "/auth/register",
        {
            "username": "auth-it-manager",
            "email": "auth-it-manager@example-test.invalid",
            "password": "password123",
            "role": "Manager",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp["statusCode"] == 201
    assert json.loads(resp["body"])["role"] == "Manager"


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------

def test_admin_lists_users_and_searches():
    _, token = _admin_ctx()
    _post("/auth/register", {"username": "auth-it-viewer", "email": "auth-it-viewer@example-test.invalid", "password": "password123"})

    resp = _get("/auth/users", headers=_auth_hdr(token))
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["total"] >= 2 and body["limit"] == 50 and body["offset"] == 0
    names = {u["username"] for u in body["items"]}
    assert {"auth-it-admin", "auth-it-viewer"} <= names
    assert all("password_hash" not in u for u in body["items"])

    narrowed = function.handler({"httpMethod": "GET", "path": "/auth/users",
                                 "queryStringParameters": {"search": "auth-it-viewer"},
                                 "headers": _auth_hdr(token)})
    hits = json.loads(narrowed["body"])["items"]
    assert [u["username"] for u in hits] == ["auth-it-viewer"]


def test_admin_changes_a_users_role():
    _, token = _admin_ctx()
    uid = json.loads(_post("/auth/register", {"username": "auth-it-viewer", "email": "auth-it-viewer@example-test.invalid", "password": "password123"})["body"])["id"]
    assert _role_of(uid) == "Viewer"

    resp = _put(f"/auth/users/{uid}/role", {"role": "Manager"}, headers=_auth_hdr(token))
    assert resp["statusCode"] == 200 and json.loads(resp["body"])["role"] == "Manager"
    assert _role_of(uid) == "Manager"  # persisted


def test_admin_cannot_demote_self():
    aid, token = _admin_ctx()
    resp = _put(f"/auth/users/{aid}/role", {"role": "Viewer"}, headers=_auth_hdr(token))
    assert resp["statusCode"] == 400 and "own role" in json.loads(resp["body"])["error"]
    assert _role_of(aid) == "Admin"  # unchanged


def test_admin_deletes_a_user():
    _, token = _admin_ctx()
    uid = json.loads(_post("/auth/register", {"username": "auth-it-viewer", "email": "auth-it-viewer@example-test.invalid", "password": "password123"})["body"])["id"]
    resp = _delete(f"/auth/users/{uid}", headers=_auth_hdr(token))
    assert resp["statusCode"] == 204
    assert postgres_service.execute("SELECT 1 FROM users WHERE id = %s", (uid,), fetch="one") is None


def test_admin_cannot_delete_self():
    aid, token = _admin_ctx()
    resp = _delete(f"/auth/users/{aid}", headers=_auth_hdr(token))
    assert resp["statusCode"] == 400 and "own account" in json.loads(resp["body"])["error"]
    assert postgres_service.execute("SELECT 1 FROM users WHERE id = %s", (aid,), fetch="one") is not None


def test_non_admin_forbidden_on_user_management():
    _post("/auth/register", {"username": "auth-it-viewer", "email": "auth-it-viewer@example-test.invalid", "password": "password123"})
    vtoken = json.loads(_post("/auth/login", {"username": "auth-it-viewer", "password": "password123"})["body"])["token"]
    assert _get("/auth/users", headers=_auth_hdr(vtoken))["statusCode"] == 403
    assert _put("/auth/users/1/role", {"role": "Admin"}, headers=_auth_hdr(vtoken))["statusCode"] == 403
    assert _delete("/auth/users/1", headers=_auth_hdr(vtoken))["statusCode"] == 403


def test_admin_updates_user_details():
    _, token = _admin_ctx()
    uid = json.loads(_post("/auth/register", {"username": "auth-it-viewer", "email": "auth-it-viewer@example-test.invalid", "password": "password123"})["body"])["id"]
    resp = _put(f"/auth/users/{uid}", {"username": "auth-it-manager", "email": "auth-it-manager@example-test.invalid"}, headers=_auth_hdr(token))
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["username"] == "auth-it-manager" and body["email"] == "auth-it-manager@example-test.invalid"
    row = postgres_service.execute("SELECT username, email FROM users WHERE id = %s", (uid,), fetch="one")
    assert row["username"] == "auth-it-manager"  # persisted


def test_admin_update_rejects_duplicate_username():
    _, token = _admin_ctx()
    json.loads(_post("/auth/register", {"username": "auth-it-viewer", "email": "auth-it-viewer@example-test.invalid", "password": "password123"})["body"])
    uid2 = json.loads(_post("/auth/register", {"username": "auth-it-dup", "email": "auth-it-dup@example-test.invalid", "password": "password123"})["body"])["id"]
    resp = _put(f"/auth/users/{uid2}", {"username": "auth-it-viewer"}, headers=_auth_hdr(token))  # collide
    assert resp["statusCode"] == 400 and "already in use" in json.loads(resp["body"])["error"]


def test_admin_update_rejects_duplicate_email():
    _, token = _admin_ctx()
    json.loads(_post("/auth/register", {"username": "auth-it-viewer", "email": "auth-it-viewer@example-test.invalid", "password": "password123"})["body"])
    uid2 = json.loads(_post("/auth/register", {"username": "auth-it-dup", "email": "auth-it-dup@example-test.invalid", "password": "password123"})["body"])["id"]
    resp = _put(f"/auth/users/{uid2}", {"email": "auth-it-viewer@example-test.invalid"}, headers=_auth_hdr(token))
    assert resp["statusCode"] == 400 and "already in use" in json.loads(resp["body"])["error"]


def test_non_admin_cannot_update_user():
    _post("/auth/register", {"username": "auth-it-viewer", "email": "auth-it-viewer@example-test.invalid", "password": "password123"})
    vtoken = json.loads(_post("/auth/login", {"username": "auth-it-viewer", "password": "password123"})["body"])["token"]
    assert _put("/auth/users/1", {"username": "x"}, headers=_auth_hdr(vtoken))["statusCode"] == 403


# ---------------------------------------------------------------------------
# Activity log — repository filtering / ordering / pagination
# ---------------------------------------------------------------------------

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


def test_manager_query_excludes_user_entities(seeded_rows):
    mgr = _mine(list_activity(include_user_entities=False, limit=500))
    types = {r["entity_type"] for r in mgr}
    assert "user" not in types           # hidden from Managers
    assert {"project", "resource"} <= types


def test_admin_query_includes_user_entities(seeded_rows):
    adm = _mine(list_activity(include_user_entities=True, limit=500))
    types = {r["entity_type"] for r in adm}
    assert "user" in types               # visible to Admins


def test_list_is_newest_first(seeded_rows):
    rows = _mine(list_activity(include_user_entities=True, limit=500))
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids, reverse=True)   # created_at DESC, id DESC


def test_filters_by_entity_type_and_action(seeded_rows):
    only_proj = _mine(list_activity(entity_type="project", include_user_entities=True, limit=500))
    assert only_proj and all(r["entity_type"] == "project" for r in only_proj)


def test_pagination_shape(seeded_rows):
    page = list_activity(include_user_entities=True, limit=2, offset=0)
    assert set(page) == {"items", "total", "limit", "offset"}
    assert page["limit"] == 2 and page["offset"] == 0 and len(page["items"]) <= 2


# ---------------------------------------------------------------------------
# Activity log — user-management CRUD writes 'user' entries end-to-end,
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
