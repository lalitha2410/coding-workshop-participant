"""
Root test fixtures shared by every service suite.

pytest loads this file (it sits at the rootdir shared by all services) before
each service's own tests/conftest.py, so these fixtures are available everywhere
without being redefined per service. Service modules are imported lazily inside
the fixtures, after each service's conftest has put its directory on sys.path.
"""

import pytest

import testkit


@pytest.fixture
def repo(monkeypatch):
    """A recorder that stubs the service's repository calls (see testkit)."""
    return testkit.make_repo_stub(monkeypatch)


@pytest.fixture
def admin_auth(monkeypatch):
    """Wrap ``function.handler`` so any event WITHOUT its own ``headers`` is
    treated as an authenticated Admin. CRUD services opt in via an autouse stub
    in their conftest; tests that set ``headers`` explicitly (even ``{}``) keep
    full control, which is how the RBAC/security tests assert 401/403.
    """
    import function
    import auth
    original = function.handler
    token = auth.create_token({"sub": "0", "username": "test-admin", "role": "Admin"})
    # No real user row exists in unit tests, so treat the subject as present;
    # individual tests override this to assert the deleted-user (401) path.
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: True)

    def wrapper(event=None, context=None):
        event = event or {}
        if "headers" not in event:
            event = {**event, "headers": {"Authorization": f"Bearer {token}"}}
        return original(event, context)

    monkeypatch.setattr(function, "handler", wrapper)
