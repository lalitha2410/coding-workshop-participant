#!/usr/bin/env bash
# Measure backend test coverage — LINE and BRANCH — per service and combined.
#
# Each service is measured in its own pytest process (their modules share names),
# then the per-service data files are combined into one report + HTML.
#
# Usage:
#   bin/coverage.sh                 # every service (term reports) + combined + HTML
#   bin/coverage.sh projects        # a single service, term report only
#
# Config lives in backend/.coveragerc (branch=on; vendored deps + tests omitted).
# Requires pytest-cov (in each service's requirements-dev.txt).
#
# View the HTML report:  open backend/htmlcov/index.html
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd -P)"
cd "$ROOT/backend"

export POSTGRES_NAME="${POSTGRES_NAME:-projectdb}"
export IS_LOCAL="${IS_LOCAL:-true}"

SERVICES=(auth projects deliverables resources allocations)

measure() {  # <service>
  local svc="$1"
  COVERAGE_FILE=".cov/$svc" python3 -m pytest "$svc/tests" \
    --cov="$svc" --cov-config=.coveragerc --cov-report=term-missing -q
}

# Single-service form.
if [[ -n "${1:-}" ]]; then
  mkdir -p .cov
  measure "$1"
  exit $?
fi

# Full sweep.
rm -rf .cov && mkdir -p .cov
for svc in "${SERVICES[@]}"; do
  echo "════════════════════════════════════════════════  $svc"
  measure "$svc"
done

echo "════════════════════════════════════════════════  COMBINED"
# --keep so the per-service files survive for re-reporting.
coverage combine --keep --data-file=.cov/combined \
  .cov/auth .cov/projects .cov/deliverables .cov/resources .cov/allocations >/dev/null
coverage report --data-file=.cov/combined --rcfile=.coveragerc
coverage html --data-file=.cov/combined --rcfile=.coveragerc -d htmlcov >/dev/null
echo
echo "Combined counts shared modules (auth.py, activity.py, pagination.py, …) once"
echo "per service, so the raw TOTAL understates them — their true coverage is the"
echo "union across services. HTML report: backend/htmlcov/index.html"
