#!/usr/bin/env bash
# Script: Vendor Python dependencies for local hot-reload
# Purpose: Install each Python backend service's requirements INTO its own folder.
#          LocalStack hot-reload runs each Lambda directly from its source folder
#          (not the Terraform-built zip), so third-party deps (psycopg, PyJWT,
#          bcrypt, ...) must live in the folder or `import` fails at runtime.
#          Cloud deploys install deps into the zip via Terraform's
#          pip_requirements and do not need this.
# Usage:   ./vendor-deps.sh
# Idempotent: skips a service whose requirements.txt is unchanged since the last
#             run (and whose deps are still present).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" > /dev/null 2>&1 && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." > /dev/null 2>&1 && pwd -P)"
BACKEND_DIR="$PROJECT_ROOT/backend"

shopt -s nullglob
installed=0
for req in "$BACKEND_DIR"/*/requirements.txt; do
    svc_dir="$(dirname "$req")"
    svc_name="$(basename "$svc_dir")"
    # Skip underscore/dot-prefixed folders (ignored by Terraform service discovery).
    case "$svc_name" in
        _*|.*) continue ;;
    esac

    hash_now="$(md5sum "$req" | cut -d' ' -f1)"
    hash_file="$svc_dir/.pip_installed"
    # psycopg is a dep of every service; use it as a sentinel so a wiped deps
    # folder forces a reinstall even when the hash file still matches.
    if [ -f "$hash_file" ] && [ "$(cat "$hash_file")" = "$hash_now" ] && [ -d "$svc_dir/psycopg" ]; then
        echo "  $svc_name: dependencies already vendored (up to date)"
        continue
    fi

    echo "  $svc_name: installing dependencies into service folder..."
    python3 -m pip install --quiet --upgrade --target="$svc_dir" -r "$req"
    echo "$hash_now" > "$hash_file"
    installed=$((installed + 1))
done

echo "Done. Vendored dependencies for $installed service(s)."
