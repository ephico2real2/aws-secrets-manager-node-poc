#!/usr/bin/env bash
# The alert paths, end to end, against a running local stack:
#   - no unexpected-read alarm from the app, rotation or tooling reads;
#   - the app's rotation notification reaches chat only (the chat topic);
#   - reading a secret as an intruder raises the stack's EventBridge rule,
#     delivered by email, SMS and chat; reading the DB secret by name doesn't
#     (the documented gap);
#   - the test alert reaches every channel; recipients are always masked.
#
#   scripts/alerts-check.sh compose http://localhost:3000
#   scripts/alerts-check.sh k8s     http://localhost:3000     (sns-logger read through kubectl exec)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
MODE="${1:-compose}"
BASE="${2:-http://localhost:3000}"
K="${KUBECTL:-kubectl}"
NS="${NAMESPACE:-secure-notes}"
fails=0

sns_get() {
  if [ "$MODE" = k8s ]; then "$K" -n "$NS" exec deploy/sns-logger -- wget -qO- "http://127.0.0.1:4575$1"
  else curl -fsS --max-time 5 "${SNS_BASE:-http://localhost:4575}$1"; fi
}
# deliveries <topic> [regex] [exclude-regex] -> the protocols ("email https sms") delivered
# for matching messages; only deliveries after $SINCE (a sequence number) count.
SINCE=0
deliveries() {
  sns_get "/_sns/deliveries?since=$SINCE" | node -e '
    let s = ""; process.stdin.on("data", (c) => (s += c)).on("end", () => {
      const [topic, re, not] = process.argv.slice(1);
      const text = (d) => `${d.subject ?? ""} ${d.body}`;
      const ds = JSON.parse(s).deliveries.filter((d) => d.topicName === topic && (!re || new RegExp(re).test(text(d))) && (!not || !new RegExp(not).test(text(d))));
      console.log([...new Set(ds.map((d) => d.protocol))].sort().join(" "));
    });' "$@"
}
# The newest delivery's sequence number: each step below judges only what it caused,
# so the check also passes after someone has clicked around the dashboard.
latest() {
  SINCE=0 sns_get /_sns/deliveries | node -e '
    let s = ""; process.stdin.on("data", (c) => (s += c)).on("end", () => console.log(Math.max(0, ...JSON.parse(s).deliveries.map((d) => d.seq))));'
}
wait_for() { # wait_for <topic> <regex> <expected protocols>
  for _ in $(seq 1 20); do [ "$(deliveries "$1" "$2")" = "$3" ] && return 0; sleep 1; done
  echo "    got: '$(deliveries "$1" "$2")'"; return 1
}
ok() { echo "  ok    $*"; }
bad() { echo "  FAIL  $*"; fails=$((fails + 1)); }
post() { curl -fsS -X POST -H 'Content-Type: application/json' -d "${2:-{\}}" "$BASE$1" >/dev/null || bad "POST $1 failed"; }
READ_TOPIC=secure-notes-secret-read-alert
OPS_TOPIC=secure-notes-ops-alerts
CHAT_TOPIC=secure-notes-ops-chat

# Reads by the lab's intruders (mallory, ops-admin) are expected alarms; any other is not.
INTRUDERS='user/mallory|assumed-role/ops-admin'
if [ -z "$(deliveries $READ_TOPIC "" "$INTRUDERS")" ]; then ok "no unexpected-read alert except the lab's intruders: the app, rotation and tooling reads are all expected"
else bad "an unexpected-read alert fired without an intruder: $(deliveries $READ_TOPIC "" "$INTRUDERS")"; fi
if wait_for $CHAT_TOPIC "rotated credential" "https" && [ -z "$(deliveries $OPS_TOPIC "rotated credential")" ]; then
  ok "the smoke test's rotations sent a notification to the chat-only topic, not the paging one (it tells, it doesn't page)"
else bad "no rotation notification on chat, or one on the paging topic"; fi

SINCE=$(latest)
post /api/demo/unexpected-read '{"as":"user","target":"redis"}'
if wait_for $READ_TOPIC "user/mallory" "email https sms"; then ok "reading the Redis secret as IAM user mallory raised the alarm: email, SMS and chat delivered"
else bad "the unexpected read raised no alarm"; fi
SINCE=$(latest)
post /api/demo/unexpected-read '{"as":"user","target":"db-by-name"}'
sleep 3
if [ -z "$(deliveries $READ_TOPIC notes-db)" ]; then ok "reading the DB secret by name is audited but not alarmed (the documented gap)"
else bad "a by-name read of the DB secret alarmed: did the rule change?"; fi
SINCE=$(latest)
# One test alert a minute (it pages by SMS): wait out a recent click.
for _ in $(seq 1 14); do
  code=$(curl -sS -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' "$BASE/api/demo/alerts/test")
  [ "$code" = 429 ] || break; sleep 5
done
[ "$code" = 200 ] || bad "POST /api/demo/alerts/test answered $code"
if wait_for $OPS_TOPIC "Test alert" "email https sms"; then ok "the test alert reached email, SMS and chat"
else bad "the test alert did not reach every channel"; fi
# Masked in the deliveries and in the SNS API's subscription lists (the full
# addresses exist only in the console's own memory).
SIG='Authorization: AWS4-HMAC-SHA256 Credential=local-tooling/20260101/us-east-1/sns/aws4_request, SignedHeaders=host, Signature=local'
list_subs() {
  if [ "$MODE" = k8s ]; then "$K" -n "$NS" exec deploy/sns-logger -- wget -qO- --header "$SIG" --post-data 'Action=ListSubscriptions' http://127.0.0.1:4575/
  else curl -fsS --max-time 5 -H "$SIG" -d 'Action=ListSubscriptions' "${SNS_BASE:-http://localhost:4575}/"; fi
}
if { SINCE=0 sns_get /_sns/export; list_subs; } | grep -qE 'oncall@example\.com|\+15555550100|hooks/secure-notes'; then bad "a full recipient (email, phone or webhook) is visible"
else ok "recipients are masked in every delivery and in the subscription lists"; fi

exit $((fails > 0))
