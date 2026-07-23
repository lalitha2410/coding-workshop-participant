"""
Setup for the performance suite.

This suite lives in its own directory and imports the repository layer of every
service directly (repository module names are distinct, and the shared
postgres_service is identical everywhere, so they co-exist in one process). It
runs against the local database defined by the POSTGRES_* env vars:

    POSTGRES_NAME=projectdb pytest -m performance

It is opt-in: the normal per-service suites never collect this directory, and
`pytest -m "not performance"` excludes it explicitly.
"""

import os
import sys
import time
import statistics

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(_HERE)
# Put every service dir on the path so the *_repository modules import, plus the
# backend dir for the shared testkit / postgres_service.
for _name in ("projects", "deliverables", "resources", "allocations", "auth"):
    _p = os.path.join(BACKEND_DIR, _name)
    if _p not in sys.path:
        sys.path.insert(0, _p)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


@pytest.fixture
def timer():
    """Return median-milliseconds of running `fn` `runs` times (after warmup)."""
    def _median_ms(fn, runs=25, warmup=3):
        for _ in range(warmup):
            fn()
        samples = []
        for _ in range(runs):
            start = time.perf_counter()
            fn()
            samples.append((time.perf_counter() - start) * 1000.0)
        median = statistics.median(samples)
        # Printed so `pytest -s` surfaces the actual numbers.
        print(f"    [perf] {getattr(fn, '__label__', 'op')}: median={median:.2f}ms "
              f"p95={sorted(samples)[int(len(samples) * 0.95)]:.2f}ms over {runs} runs")
        return median
    return _median_ms


@pytest.fixture
def seeded_projects():
    """Seed a few hundred rows tagged for cleanup, so list queries face a larger
    table (exercises the indexes). Yields (department_tag, count) and removes the
    rows afterwards."""
    from projects_repository import create_project, delete_project, list_projects

    tag = "PERF-SEED"
    ids = [create_project({"name": f"perf-seed-{i}", "department": tag})["id"] for i in range(500)]
    try:
        yield {"tag": tag, "count": len(ids), "list_projects": list_projects}
    finally:
        for pid in ids:
            delete_project(pid)
