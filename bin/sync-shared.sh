#!/usr/bin/env bash
# Script: Sync shared backend modules
# Purpose: Propagate canonical modules from backend/_shared into each backend
#          service folder, so every Lambda bundles its own copy (each service is
#          packaged only from its own directory, and local hot-reload uploads
#          only that folder).
# Usage:   ./sync-shared.sh
#
# Edit shared code ONLY in backend/_shared; run this to propagate. Idempotent —
# safe to run repeatedly. Generated copies are header-marked "DO NOT EDIT".
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" > /dev/null 2>&1 && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." > /dev/null 2>&1 && pwd -P)"
BACKEND_DIR="$PROJECT_ROOT/backend"
SHARED_DIR="$BACKEND_DIR/_shared"

if [ ! -d "$SHARED_DIR" ]; then
    echo "ERROR: shared dir not found: $SHARED_DIR" >&2
    exit 1
fi

shopt -s nullglob
shared_files=("$SHARED_DIR"/*.py)
if [ ${#shared_files[@]} -eq 0 ]; then
    echo "WARN: no shared .py modules in $SHARED_DIR — nothing to sync"
    exit 0
fi

synced=0
# A service folder is any backend/*/ with a requirements.txt, skipping folders
# prefixed with '_' or '.' (ignored by Terraform service discovery).
for req in "$BACKEND_DIR"/*/requirements.txt; do
    [ -e "$req" ] || continue
    svc_dir="$(dirname "$req")"
    svc_name="$(basename "$svc_dir")"
    case "$svc_name" in
        _*|.*) continue ;;
    esac

    for src in "${shared_files[@]}"; do
        fname="$(basename "$src")"
        dest="$svc_dir/$fname"
        {
            echo "# ============================================================"
            echo "# GENERATED FILE - DO NOT EDIT"
            echo "# Source of truth: backend/_shared/$fname"
            echo "# Regenerate with: bin/sync-shared.sh"
            echo "# ============================================================"
            cat "$src"
        } > "$dest"
        echo "  synced backend/$svc_name/$fname"
        synced=$((synced + 1))
    done
done

echo "Done. Synced $synced file(s) into backend services."
