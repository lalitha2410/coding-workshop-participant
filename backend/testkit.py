"""
Shared, dependency-light test helpers used by every service's suite.

This removes setup that was previously copy-pasted across all five services:
the Lambda-proxy event builder, the JSON-body parser, the bearer-token header,
the DB-readiness probe, and the repository stub recorder.

Service-specific modules (``function``, ``auth``, ``postgres_service``) are
imported lazily inside the helpers so this module stays generic and importable
from any service's process (each service puts its own directory first on
sys.path, so a lazy ``import function`` resolves to the right service).
"""

import json


def parse_body(response):
    """Parse the JSON body of a handler response (empty string -> None)."""
    raw = response.get("body")
    return json.loads(raw) if raw else None


def make_event(method, path, *, body=None, headers=None, query=None, path_params=None):
    """Build an API-Gateway-style Lambda-proxy event.

    ``body`` may be a dict (JSON-encoded) or a raw string (passed through, e.g. to
    test malformed JSON). Omitted sections are left off entirely so tests can
    assert behaviour when ``headers``/``queryStringParameters`` are absent.
    """
    event = {"httpMethod": method, "path": path}
    if body is not None:
        event["body"] = body if isinstance(body, str) else json.dumps(body)
    if headers is not None:
        event["headers"] = headers
    if query is not None:
        event["queryStringParameters"] = query
    if path_params is not None:
        event["pathParameters"] = path_params
    return event


def bearer(role="Admin", sub="1", username="u"):
    """An Authorization header dict carrying a freshly-signed JWT for ``role``."""
    import auth
    token = auth.create_token({"sub": str(sub), "username": username, "role": role})
    return {"Authorization": f"Bearer {token}"}


def database_ready(table):
    """True if the local database is reachable and ``table`` exists.

    Used by integration/performance modules to skip cleanly when no DB is
    available, so the unit/api/security suites still run anywhere.
    """
    import postgres_service
    try:
        postgres_service.execute(f"SELECT 1 FROM {table} LIMIT 1", fetch="one")
        return True
    except Exception:
        # Reset the pooled connection so a failed probe doesn't poison later calls.
        postgres_service.PG_CONN = None
        return False


def make_repo_stub(monkeypatch):
    """Replace repository calls on the ``function`` module with a recorder.

    ``repo.set(name, value)`` stubs ``function.<name>`` to return ``value`` (or
    raise it, if it's an Exception) and record how it was called; ``repo.calls``
    exposes the recorded ``{args, kwargs}`` per name.
    """
    import function
    calls = {}

    def record(name, return_value):
        def _fn(*args, **kwargs):
            calls[name] = {"args": args, "kwargs": kwargs}
            if isinstance(return_value, Exception):
                raise return_value
            return return_value
        return _fn

    class Repo:
        def set(self, name, return_value):
            monkeypatch.setattr(function, name, record(name, return_value))

        @property
        def calls(self):
            return calls

    return Repo()
