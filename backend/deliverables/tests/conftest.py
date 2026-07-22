"""
Shared pytest configuration for the deliverables service tests.

Adds the service directory (one level up) to sys.path so tests can import the
service modules (function, deliverables_repository, validation, postgres_service)
directly, the same way they are imported at Lambda runtime.
"""

import os
import sys

SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)
