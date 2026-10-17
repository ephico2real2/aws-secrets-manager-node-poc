#!/usr/bin/env bash
# Wait for the Docker Compose stack, then run the end-to-end smoke test.
#
#   docker compose up -d && scripts/compose-check.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
BASE="${1:-http://localhost:3000}"

echo "== waiting for $BASE/api/health"
for i in $(seq 1 90); do
  if curl -fsS --max-time 3 "$BASE/api/health" 2>/dev/null | grep -q '"status":"ok"'; then
    echo "  ready after ~$((i * 2)) s"; break
  fi
  [ "$i" = 90 ] && { echo "  not ready after 180 s"; docker compose ps; exit 1; }
  sleep 2
done
docker compose ps --format 'table {{.Service}}\t{{.Image}}\t{{.State}}'

echo "== the seed job burned the bootstrap passwords"
fails=0
if docker compose exec -T redis redis-cli --no-auth-warning --user default --pass bootstrap-only-change-me ping 2>&1 | grep -q PONG; then
  echo "  FAIL  Redis still accepts the bootstrap password"; fails=$((fails + 1))
else
  echo "  ok    Redis rejects the bootstrap password"
fi

echo "== end-to-end smoke test"
node backend/scripts/smoke-test.js "$BASE" || fails=$((fails + 1))
exit $((fails > 0))
