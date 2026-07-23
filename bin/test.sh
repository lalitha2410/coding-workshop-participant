#!/usr/bin/env bash
# Run the backend test suites.
#
# Each service is run in its own pytest process (their modules share names like
# function.py and can't co-exist in one process), so "run everything" loops the
# services and aggregates the result.
#
# Usage:
#   bin/test.sh                      # every service, full suite
#   bin/test.sh -m unit              # only unit tests, every service
#   bin/test.sh -m "not integration" # skip DB tests, every service
#   bin/test.sh -m security          # markers: unit | integration | api | security
#   bin/test.sh projects             # a single service, full suite
#   bin/test.sh projects -m api      # a single service, one marker
#   bin/test.sh performance          # the opt-in performance suite (DB-backed)
#
# Any extra args are passed straight through to pytest (e.g. -v, -x, -k name).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd -P)"

# Integration/performance tests target the local dev database; default to the
# test DB and local (non-SSL) connection unless the caller overrides.
export POSTGRES_NAME="${POSTGRES_NAME:-projectdb}"
export IS_LOCAL="${IS_LOCAL:-true}"

SERVICES=(auth projects deliverables resources allocations)

run_one() {  # <dir> <label> <pytest args...>
  local dir="$1"; local label="$2"; shift 2
  echo "──────────────────────────────────────────────  $label"
  ( cd "$ROOT/backend/$dir" && python3 -m pytest "$@" )
}

# Single-target forms: `test.sh <service> [args]` or `test.sh performance [args]`.
if [[ "${1:-}" == "performance" ]]; then
  shift
  run_one performance "performance" -m performance "$@"
  exit $?
fi
for svc in "${SERVICES[@]}"; do
  if [[ "${1:-}" == "$svc" ]]; then
    shift
    run_one "$svc" "$svc" "$@"
    exit $?
  fi
done

# Default: loop every service, pass through args, aggregate.
failed=()
for svc in "${SERVICES[@]}"; do
  if run_one "$svc" "$svc" "$@"; then :; else failed+=("$svc"); fi
done

echo "════════════════════════════════════════════════"
if [[ ${#failed[@]} -eq 0 ]]; then
  echo "All service suites passed."
else
  echo "FAILED: ${failed[*]}"
  exit 1
fi
