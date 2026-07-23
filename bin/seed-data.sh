#!/usr/bin/env bash
# Script: Seed realistic demo data
# Purpose: Populate the database the backend Lambdas use with realistic sample
#          data (projects, resources, deliverables, allocations) plus per-role
#          demo users for exercising RBAC. Idempotent / re-runnable.
# Usage:   ./seed-data.sh
#
# Targets the SAME database the deployed Lambdas read — see infra/locals.tf:
#   db "postgres", user "postgres", password "postgres123", port 5432.
# The Lambdas reach it at host 172.17.0.1 (docker bridge); from the host we use
# localhost — same PostgreSQL server. Override any of these with POSTGRES_* env.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" > /dev/null 2>&1 && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." > /dev/null 2>&1 && pwd -P)"
BACKEND_DIR="$PROJECT_ROOT/backend"
SEED_SQL="$BACKEND_DIR/db/seed.sql"

PGHOST="${POSTGRES_HOST:-localhost}"
PGPORT="${POSTGRES_PORT:-5432}"
PGUSER="${POSTGRES_USER:-postgres}"
PGDATABASE="${POSTGRES_NAME:-postgres}"
export PGPASSWORD="${POSTGRES_PASS:-postgres123}"

PSQL=(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 -q)

echo "======================================"
echo "LoadBalance — seeding demo data"
echo "  target: $PGUSER@$PGHOST:$PGPORT/$PGDATABASE"
echo "======================================"

# 1) Domain data (projects / resources / deliverables / allocations).
echo "INFO: Seeding domain tables from $(basename "$SEED_SQL")..."
"${PSQL[@]}" -f "$SEED_SQL"

# 2) One demo user per role, each with its own known password, so every RBAC
#    level can be exercised. Hashes are generated with the bcrypt vendored into
#    backend/auth (the exact library the Lambda verifies against).
echo "INFO: Upserting per-role demo users..."

# username : password : role : email   (one login per role)
DEMO_USERS=(
  "admin:admin123:Admin:admin@acme.test"
  "manager:manager123:Manager:manager@acme.test"
  "contributor:contributor123:Contributor:contributor@acme.test"
  "viewer:viewer123:Viewer:viewer@acme.test"
)

gen_hash() {
  PYTHONPATH="$BACKEND_DIR/auth" python3 -c \
    "import bcrypt,sys; sys.stdout.write(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())" "$1" 2>/dev/null || true
}

# Drop demo users from earlier iterations to keep the login list clean.
"${PSQL[@]}" -c "DELETE FROM users WHERE username IN ('meridian.admin','meridian.manager','meridian.editor');" > /dev/null

seeded_users=0
for entry in "${DEMO_USERS[@]}"; do
  IFS=':' read -r uname pass role email <<< "$entry"
  hash="$(gen_hash "$pass")"
  if [[ "$hash" == \$2* ]]; then
    "${PSQL[@]}" -v uname="$uname" -v email="$email" -v hash="$hash" -v role="$role" <<'SQL'
INSERT INTO users (username, email, password_hash, role_id)
VALUES (:'uname', :'email', :'hash', (SELECT id FROM roles WHERE name = :'role'))
ON CONFLICT (username) DO UPDATE
  SET email = EXCLUDED.email, password_hash = EXCLUDED.password_hash, role_id = EXCLUDED.role_id;
SQL
    seeded_users=$((seeded_users + 1))
  else
    echo "  WARN: bcrypt unavailable — could not seed user '$uname'."
  fi
done
echo "  seeded ${seeded_users} demo user(s)."

# 3) Summary counts.
echo ""
echo "Seeded:"
"${PSQL[@]}" -tA -c "SELECT '  projects: '||count(*) FROM projects
  UNION ALL SELECT '  resources: '||count(*) FROM resources
  UNION ALL SELECT '  deliverables: '||count(*) FROM deliverables
  UNION ALL SELECT '  allocations: '||count(*) FROM allocations
  UNION ALL SELECT '  over-allocated people: '||count(*) FROM (
    SELECT resource_id FROM allocations GROUP BY resource_id HAVING SUM(allocation_pct) > 100
  ) o;"
echo ""
echo "Demo logins (username / password -> role):"
echo "  admin       / admin123        -> Admin        (full access, incl. Users)"
echo "  manager     / manager123      -> Manager      (full CRUD, incl. delete)"
echo "  contributor / contributor123  -> Contributor  (create + edit, no delete)"
echo "  viewer      / viewer123       -> Viewer       (read-only)"
echo ""
echo "✓ Done."
