"""
pytest setup for the allocations service tests.

Puts the service directory (for `function`, `allocations_repository`, `validation`,
`postgres_service`, …) and the backend directory (for the shared `testkit`) on
sys.path, then opts this service's handler tests into the shared Admin-token
injection defined in backend/conftest.py.
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


@pytest.fixture(autouse=True)
def _default_admin_auth(admin_auth):
    """Handler tests run as Admin unless they set their own headers (see admin_auth)."""
