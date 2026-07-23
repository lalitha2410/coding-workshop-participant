"""
pytest setup for the auth service tests.

Puts the service directory (for `function`, `users_repository`, `validation`,
`auth`, `postgres_service`, …) and the backend directory (for the shared
`testkit`) on sys.path, mirroring how modules are imported at Lambda runtime.

Unlike the CRUD services, auth manages its own authentication in every test, so
this conftest deliberately does NOT opt into the autouse Admin-token injection
(`_default_admin_auth`) — each auth test supplies the tokens it needs. The one
shared fixture defined here is `bypass_user_check`, used by both test_api.py and
test_security.py to treat the token subject as a still-existing user.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE_DIR = os.path.dirname(_HERE)
BACKEND_DIR = os.path.dirname(SERVICE_DIR)
for _p in (BACKEND_DIR, SERVICE_DIR):  # SERVICE_DIR inserted last -> ends up first
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest


@pytest.fixture
def bypass_user_check(monkeypatch):
    """The admin routes verify the token's user still exists (DB); bypass in unit tests."""
    import function
    monkeypatch.setattr(function.auth, "db_user_exists", lambda uid: True)
