#!/usr/bin/env bash
# Photograph a lab running on this machine with the walk CI uses (scripts/capture/walk.js):
# each page states the text it must show, so a capture of a broken page fails (exit 2),
# exactly as in CI. Playwright and js-yaml at the pins in scripts/versions.env, installed
# once into .tmp/pw (the folder CI's browser-walk action uses). Nothing is published.
#
#   scripts/capture-local.sh compose     # the dashboard walk, on Docker Compose
#   scripts/capture-local.sh kind        # the same walk, on kind
#   scripts/capture-local.sh alerts      # the notification console (needs a few deliveries: demo 13, 14)
#   scripts/capture-local.sh reveal      # the reveal flag on (LOG_REVEAL_SECRETS=true; demo 7)
#   OUT=demo/new scripts/capture-local.sh kind
#
# The dashboard walk clicks like a presenter: it rotates both secrets and runs the leak test.
# PNGs and walk.log go to $OUT (default .tmp/captures/<target>).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. scripts/versions.env

target="${1:-compose}"
export BASE="${BASE:-http://localhost:3000}" SNS_BASE="${SNS_BASE:-http://localhost:4575}"
case "$target" in
  # The labels are the ones the dashboard prints on each platform (the same as CI's walks).
  compose) spec=scripts/capture/dashboard.yaml; export PLATFORM_LABEL="dummy keys, for the mock only" ;;
  kind)    spec=scripts/capture/dashboard.yaml; export PLATFORM_LABEL="no SA token · restricted PSA" ;;
  alerts)  spec=scripts/capture/alerts.yaml ;;
  reveal)  spec=scripts/capture/reveal.yaml ;;
  *) echo "usage: $0 compose|kind|alerts|reveal" >&2; exit 2 ;;
esac
OUT="${OUT:-.tmp/captures/$target}"
PW=.tmp/pw

have=$(node -p "try { require('./$PW/node_modules/playwright/package.json').version } catch { '' }" 2>/dev/null || true)
if [ "$have" != "$PLAYWRIGHT_VERSION" ]; then
  echo "== Playwright $PLAYWRIGHT_VERSION and js-yaml $JS_YAML_VERSION into $PW"
  mkdir -p "$PW"
  (cd "$PW" && { [ -f package.json ] || npm init -y >/dev/null; } \
     && npm i --no-audit --no-fund "playwright@$PLAYWRIGHT_VERSION" "js-yaml@$JS_YAML_VERSION" >/dev/null)
fi
(cd "$PW" && npx playwright install chromium >/dev/null)   # a no-op when this release's Chromium is cached

mkdir -p "$OUT"
echo "== walk $spec against $BASE -> $OUT"
set +e
S="$OUT" NODE_PATH="$PWD/$PW/node_modules" node scripts/capture/walk.js "$spec" 2>&1 | tee "$OUT/walk.log"
rc=${PIPESTATUS[0]}
set -e
ls "$OUT"/*.png 2>/dev/null | sed 's/^/  /'
exit "$rc"
