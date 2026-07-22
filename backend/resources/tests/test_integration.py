"""
Integration tests for the resources service against a real local PostgreSQL.

These hit the database defined by the POSTGRES_* env vars (defaults:
localhost:5432, postgres/postgres, projectdb) and run through the repository
layer. Resources have no FK dependencies, but `email` is UNIQUE, so tests use
distinctive emails and clean up every row they create. The whole module
auto-skips when the DB or schema is unavailable.

Run against the local dev database with the schema loaded:
    IS_LOCAL=true pytest backend/resources/tests/test_integration.py
"""

import pytest

import postgres_service
from resources_repository import (
    list_resources,
    get_resource,
    create_resource,
    update_resource,
    delete_resource,
    DuplicateEmailError,
)


def _database_ready():
    """True if we can connect and the resources table exists."""
    try:
        postgres_service.execute("SELECT 1 FROM resources LIMIT 1", fetch="one")
        return True
    except Exception:
        postgres_service.PG_CONN = None
        return False


pytestmark = pytest.mark.skipif(
    not _database_ready(),
    reason="local PostgreSQL with the resources schema is not available",
)

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


def test_create_persists(created_resource):
    assert created_resource["id"] is not None
    assert created_resource["name"] == "Integration Resource"
    assert created_resource["email"] == _EMAIL_A
    assert created_resource["created_at"] is not None


def test_get_returns_created_row(created_resource):
    fetched = get_resource(created_resource["id"])
    assert fetched is not None
    assert fetched["id"] == created_resource["id"]


def test_get_missing_returns_none():
    assert get_resource(2_000_000_000) is None


def test_list_and_search(created_resource):
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


def test_pagination_slices_and_counts():
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


def test_sql_injection_payload_stored_literally():
    payload = "'; DROP TABLE resources;--"
    created = create_resource({"name": payload, "email": "sqli-it@example-test.invalid"})
    try:
        assert get_resource(created["id"])["name"] == payload  # literal data, not executed
        assert list_resources(search="DROP TABLE", limit=10)["total"] >= 1  # table intact
    finally:
        delete_resource(created["id"])


def test_partial_update_preserves_other_fields(created_resource):
    updated = update_resource(created_resource["id"], {"title": "Staff QA Engineer"})
    assert updated["title"] == "Staff QA Engineer"
    # COALESCE partial update leaves untouched fields intact.
    assert updated["name"] == created_resource["name"]
    assert updated["email"] == _EMAIL_A


def test_update_missing_returns_none():
    assert update_resource(2_000_000_000, {"title": "x"}) is None


def test_delete_removes_row():
    resource = create_resource({"name": "To Be Deleted", "email": _EMAIL_B})
    deleted = delete_resource(resource["id"])
    assert deleted is not None and deleted["id"] == resource["id"]
    assert get_resource(resource["id"]) is None
    # Deleting again is a no-op that returns None.
    assert delete_resource(resource["id"]) is None


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
