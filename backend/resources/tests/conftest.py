"""
Shared pytest configuration for the resources service tests.

Adds the service directory (one level up) to sys.path so tests can import the
service modules (function, resources_repository, validation, postgres_service)
directly, the same way they are imported at Lambda runtime.
"""

import os
import sys

SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)


import pytest


@pytest.fixture(autouse=True)
def _default_admin_auth(monkeypatch):
    """Inject a valid Admin bearer token into any event that does not set its own
    'headers', so the existing CRUD tests exercise the real auth gate as an Admin.
    Tests that set 'headers' explicitly (even an empty dict) control auth
    themselves — used to assert 401/403 behavior."""
    import function
    import auth
    original = function.handler
    admin_token = auth.create_token({"sub": "0", "username": "test-admin", "role": "Admin"})
    # The gate checks the user still exists via the DB; in unit tests there is no
    # such user row, so treat the token subject as present by default. Individual
    # tests override this to assert the deleted-user (401) path.
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: True)

    def wrapper(event=None, context=None):
        event = event or {}
        if "headers" not in event:
            event = {**event, "headers": {"Authorization": f"Bearer {admin_token}"}}
        return original(event, context)

    monkeypatch.setattr(function, "handler", wrapper)
