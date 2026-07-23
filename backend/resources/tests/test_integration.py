"""
Integration tests — real database round-trips through the repository layer.

These hit the database defined by the POSTGRES_* env vars (defaults:
localhost:5432, postgres/postgres, projectdb). Resources have no FK
dependencies, but `email` is UNIQUE, so tests use distinctive emails and clean
up every row they create. The whole module auto-skips when the database or
`resources` table is unavailable, so the unit/api/security suites still run
anywhere.

    POSTGRES_NAME=projectdb pytest -m integration
"""

import json

import pytest

import auth
import function
import postgres_service
import testkit
from resources_repository import (
    list_resources,
    get_resource,
    create_resource,
    update_resource,
    delete_resource,
    DuplicateEmailError,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not testkit.database_ready("resources"),
        reason="local PostgreSQL with the resources schema is not available",
    ),
]

# Distinctive emails so tests never collide with real data; helper for cleanup.
_EMAIL_A = "it-resource-a@example-test.invalid"
_EMAIL_B = "it-resource-b@example-test.invalid"


def _cleanup_emails(*emails):
    for email in emails:
        postgres_service.execute("DELETE FROM resources WHERE email = %s", (email,))


@pytest.fixture
def created_resource():
    """Create a throwaway resource and guarantee cleanup afterwards."""
    _cleanup_emails(_EMAIL_A, _EMAIL_B)  # start clean in case a prior run crashed
    resource = create_resource({
        "name": "Integration Resource",
        "email": _EMAIL_A,
        "title": "QA Engineer",
    })
    yield resource
    _cleanup_emails(_EMAIL_A, _EMAIL_B)


# ---------------------------------------------------------------------------
# CRUD round-trips
# ---------------------------------------------------------------------------

def test_create_persists_row(created_resource):
    assert created_resource["id"] is not None
    assert created_resource["name"] == "Integration Resource"
    assert created_resource["email"] == _EMAIL_A
    assert created_resource["created_at"] is not None


def test_get_returns_the_created_row(created_resource):
    fetched = get_resource(created_resource["id"])
    assert fetched is not None
    assert fetched["id"] == created_resource["id"]


def test_get_missing_id_returns_none():
    assert get_resource(2_000_000_000) is None


def test_list_and_search_by_name_and_title(created_resource):
    # Search matches on name...
    by_name = list_resources(search="Integration Resource", limit=200)
    assert any(r["id"] == created_resource["id"] for r in by_name["items"])
    assert by_name["total"] >= 1 and by_name["limit"] == 200

    # ...and on title.
    by_title = list_resources(search="QA Engineer")
    assert any(r["id"] == created_resource["id"] for r in by_title["items"])

    # A non-matching search excludes the row.
    none_rows = list_resources(search="__no_such_resource__")
    assert none_rows["total"] == 0 and none_rows["items"] == []


def test_pagination_slices_pages_and_counts_total():
    emails = [f"pag-it-{i}@example-test.invalid" for i in range(3)]
    made = [create_resource({"name": f"Pag {i}", "email": e, "title": "PAGIT-ROLE"})
            for i, e in enumerate(emails)]
    try:
        page1 = list_resources(search="PAGIT-ROLE", limit=2, offset=0)
        page2 = list_resources(search="PAGIT-ROLE", limit=2, offset=2)
        assert page1["total"] == 3 and page2["total"] == 3
        assert len(page1["items"]) == 2 and len(page2["items"]) == 1
        ids1 = {r["id"] for r in page1["items"]}
        ids2 = {r["id"] for r in page2["items"]}
        assert ids1.isdisjoint(ids2)
    finally:
        for r in made:
            delete_resource(r["id"])


def test_partial_update_preserves_other_fields(created_resource):
    updated = update_resource(created_resource["id"], {"title": "Staff QA Engineer"})
    assert updated["title"] == "Staff QA Engineer"
    # COALESCE partial update leaves untouched fields intact.
    assert updated["name"] == created_resource["name"]
    assert updated["email"] == _EMAIL_A


def test_update_missing_id_returns_none():
    assert update_resource(2_000_000_000, {"title": "x"}) is None


def test_delete_removes_row_and_is_idempotent():
    resource = create_resource({"name": "To Be Deleted", "email": _EMAIL_B})
    deleted = delete_resource(resource["id"])
    assert deleted is not None and deleted["id"] == resource["id"]
    assert get_resource(resource["id"]) is None
    # Deleting again is a no-op that returns None.
    assert delete_resource(resource["id"]) is None


# ---------------------------------------------------------------------------
# Unique-email constraint
# ---------------------------------------------------------------------------

def test_create_duplicate_email_raises(created_resource):
    with pytest.raises(DuplicateEmailError):
        create_resource({"name": "Duplicate", "email": _EMAIL_A})
    # Connection remains usable after the constraint violation (execute rolls back).
    assert get_resource(created_resource["id"]) is not None


def test_update_to_existing_email_raises(created_resource):
    # Create a second resource, then try to steal the first one's email.
    other = create_resource({"name": "Other", "email": _EMAIL_B})
    try:
        with pytest.raises(DuplicateEmailError):
            update_resource(other["id"], {"email": _EMAIL_A})
    finally:
        delete_resource(other["id"])


# ---------------------------------------------------------------------------
# Activity log written through the real handler (create / update / delete)
# ---------------------------------------------------------------------------

@pytest.fixture
def actor_user():
    """A real user row (so the activity FK is satisfied) plus a token for them."""
    uid = postgres_service.execute(
        "INSERT INTO users (username, email, password_hash, role_id) "
        "VALUES (%s,%s,%s,(SELECT id FROM roles WHERE name='Admin')) RETURNING id",
        ("res-act-actor", "res-act-actor@example-test.invalid", "x"), fetch="one")["id"]
    token = auth.create_token({"sub": str(uid), "username": "res-act-actor", "role": "Admin"})
    yield {"uid": uid, "token": token}
    postgres_service.execute("DELETE FROM users WHERE id = %s", (uid,))


def _latest_activity(entity_id, action):
    return postgres_service.execute(
        "SELECT * FROM activity_log WHERE entity_type='resource' AND entity_id=%s AND action=%s "
        "ORDER BY id DESC LIMIT 1", (entity_id, action), fetch="one")


def test_create_update_delete_each_write_an_activity_entry(actor_user):
    hdr = {"Authorization": f"Bearer {actor_user['token']}"}

    created = function.handler(testkit.make_event(
        "POST", "/resources",
        body={"name": "Act Resource", "email": "act-res@example-test.invalid", "title": "Engineer"},
        headers=hdr))
    rid = json.loads(created["body"])["id"]
    try:
        row = _latest_activity(rid, "created")
        assert row and row["user_id"] == actor_user["uid"] and row["entity_name"] == "Act Resource"

        function.handler(testkit.make_event("PUT", f"/resources/{rid}", body={"title": "Staff Engineer"}, headers=hdr))
        upd = _latest_activity(rid, "updated")
        assert upd and {"field": "title", "old": "Engineer", "new": "Staff Engineer"} in upd["changes"]

        function.handler(testkit.make_event("DELETE", f"/resources/{rid}", headers=hdr))
        assert _latest_activity(rid, "deleted") is not None
    finally:
        postgres_service.execute("DELETE FROM resources WHERE id = %s", (rid,))
        postgres_service.execute("DELETE FROM activity_log WHERE entity_type='resource' AND entity_id=%s", (rid,))
