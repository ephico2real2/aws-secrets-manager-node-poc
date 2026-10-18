#!/usr/bin/env bash
# Logs first, then alerts: the local log pipeline end to end (Compose with
# docker-compose.observability.yml).
#   - every service's records reach VictoriaLogs through the collector;
#   - a real failure (Secrets Manager unreachable during a forced refresh) is
#     logged with its event, matched by a vmalert rule, routed by Alertmanager
#     and delivered by the local SNS: email, SMS and chat, within two minutes;
#   - sns-logger's Pipeline tab sees the log store.
#
#   COMPOSE_FILE=docker-compose.yml:docker-compose.observability.yml scripts/pipeline-check.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
BASE="${1:-http://localhost:3000}"
VL="${VICTORIALOGS_URL:-http://localhost:9428}"
SNS="${SNS_BASE:-http://localhost:4575}"
fails=0
ok() { echo "  ok    $*"; }
bad() { echo "  FAIL  $*"; fails=$((fails + 1)); }
count() { # count <LogsQL filter> -> number of records in the last 15 minutes
  curl -fsS --max-time 10 "$VL/select/logsql/query" --data-urlencode "query=_time:15m $1 | stats count() as n" | sed -n 's/.*"n":"\{0,1\}\([0-9]*\).*/\1/p' | head -1
}

echo "== records in VictoriaLogs (shipped as OpenTelemetry logs)"
for svc in secure-notes aws-mock sns-logger; do
  n=0
  for _ in $(seq 1 30); do n=$(count "service.name:=\"$svc\""); [ "${n:-0}" -gt 0 ] && break; sleep 2; done
  if [ "${n:-0}" -gt 0 ]; then ok "$svc: $n records"; else bad "$svc: no records reached VictoriaLogs"; fi
done
n=$(count 'event:="cloudtrail.record"')
if [ "${n:-0}" -gt 0 ]; then ok "CloudTrail-shaped records from the AWS mock: $n"; else bad "no CloudTrail records in the log store"; fi

echo "== a real failure becomes an alert: Secrets Manager unreachable during a forced refresh"
docker compose stop aws-mock >/dev/null 2>&1
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' "$BASE/api/secrets/db/refresh")
docker compose start aws-mock >/dev/null 2>&1
echo "  forced refresh with the mock stopped answered HTTP $code (the app keeps serving its cached value)"
for _ in $(seq 1 60); do
  n=$(count 'service.name:="secure-notes" event:="secrets.fetch.failed"'); [ "${n:-0}" -gt 0 ] && break; sleep 2
done
if [ "${n:-0}" -gt 0 ]; then ok "the failure is in the log store with event secrets.fetch.failed"; else bad "the failure never reached the log store"; fi
got=""
for _ in $(seq 1 60); do
  got=$(curl -fsS "$SNS/_sns/deliveries" | node -e '
    let s = ""; process.stdin.on("data", (c) => (s += c)).on("end", () => {
      const ds = JSON.parse(s).deliveries.filter((d) => d.topicName === "secure-notes-ops-alerts" && /could not be read from Secrets Manager/.test(`${d.subject ?? ""} ${d.body}`));
      console.log([...new Set(ds.map((d) => d.protocol))].sort().join(" "));
    });')
  [ "$got" = "email https sms" ] && break
  sleep 2
done
if [ "$got" = "email https sms" ]; then ok "vmalert -> Alertmanager -> SNS delivered the critical alert by email, SMS and chat"
else bad "the alert was not delivered on every channel (got '$got')"; fi
if curl -fsS "$SNS/_sns/deliveries" | grep -q 'assumed-role/alertmanager'; then ok "published by Alertmanager's identity"; else bad "no delivery published by Alertmanager"; fi

echo "== a warning goes to chat only: a burst of errors in the app log (pattern rule app.errors.burst)"
# Each forced refresh with the mock stopped logs two error lines (the fetch and the request);
# the route allows one refresh per secret every 2 s, so three of them, paced, make six: the rule wants 5 in 5m.
docker compose stop aws-mock >/dev/null 2>&1
for _ in 1 2 3; do
  sleep 2.5
  curl -s -o /dev/null -X POST -H 'Content-Type: application/json' -d '{}' "$BASE/api/secrets/db/refresh"
done
docker compose start aws-mock >/dev/null 2>&1
n=$(count 'service.name:="secure-notes" level:=error -_msg:~"^simulated:"')
echo "  error lines from the app in the log store: ${n:-0} (the rule fires at 5 in 5m)"
burst() { # the topic/protocol of every delivery of the burst alert, sorted
  curl -fsS "$SNS/_sns/deliveries" | node -e '
    let s = ""; process.stdin.on("data", (c) => (s += c)).on("end", () => {
      const ds = JSON.parse(s).deliveries.filter((d) => /Burst of errors in the app log/.test(`${d.subject ?? ""} ${d.body}`));
      console.log(ds.map((d) => `${d.topicName}/${d.protocol}`).sort().join(" "));
    });'
}
got=""
for _ in $(seq 1 60); do got=$(burst); [ -n "$got" ] && break; sleep 2; done
# Alertmanager repeats it after 1h (the catalogue's "repeat"), so a burst that keeps firing still sent one message.
if [ "$got" = "secure-notes-ops-chat/https" ]; then ok "one delivery, to the chat topic: vmalert -> Alertmanager -> SNS"
elif [ -z "$got" ]; then bad "the burst alert was never delivered"
else bad "the burst alert went to '$got', want secure-notes-ops-chat/https only"; fi
case " $got " in
  *secure-notes-ops-alerts*) bad "the warning paged (a delivery on the alerts topic)" ;;
  *) if [ -n "$got" ]; then ok "no page: nothing on the alerts topic, so no email and no SMS"; fi ;;
esac

echo "== the notification console sees the log store"
if curl -fsS "$SNS/_sns/pipeline" | grep -q '"deployed":true'; then ok "sns-logger's Pipeline tab reads VictoriaLogs"; else bad "sns-logger can't read VictoriaLogs"; fi

exit $((fails > 0))
