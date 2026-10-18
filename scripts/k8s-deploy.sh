#!/usr/bin/env bash
# Deploy an overlay and wait until the app is serving.
#
#   scripts/k8s-deploy.sh deploy/k8s/overlays/kind                  # then http://localhost:3000
#   KUBECTL=oc scripts/k8s-deploy.sh deploy/k8s/overlays/openshift   # prints the two https:// Routes
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. scripts/versions.env
OVERLAY="${1:?usage: k8s-deploy.sh <kustomize dir>}"
K="${KUBECTL:-kubectl}"
NS="${NAMESPACE}"

echo "== render $OVERLAY"
"$K" kustomize "$OVERLAY" > /tmp/secure-notes-rendered.yaml
grep -E '^kind:' /tmp/secure-notes-rendered.yaml | sort | uniq -c

# A Job's pod template is immutable; the seed is idempotent, so replace it.
"$K" -n "$NS" delete job seed --ignore-not-found --wait=true 2>/dev/null || true

echo "== apply"
"$K" apply -f /tmp/secure-notes-rendered.yaml

if grep -q '^kind: Job' /tmp/secure-notes-rendered.yaml; then
  echo "== waiting for the backing services and the seed job"
  for d in aws-mock sns-logger postgres redis; do "$K" -n "$NS" rollout status "deploy/$d" --timeout=300s; done
  if ! "$K" -n "$NS" wait --for=condition=complete job/seed --timeout=300s; then
    "$K" -n "$NS" logs job/seed --all-containers --tail=100 || true
    exit 1
  fi
  "$K" -n "$NS" logs job/seed --tail=20
fi

echo "== waiting for the app (it restarts until its secrets exist, then becomes ready)"
"$K" -n "$NS" rollout status deploy/secure-notes --timeout=420s
"$K" -n "$NS" get pods -o wide

# OpenShift: the Routes. Wait for the router to admit them, then point the
# dashboard's "notification console" link (and the console's own links) at the
# console's Route. The override is plain env on the Deployments, so the next
# apply keeps it and this script sets it again.
if grep -q '^kind: Route' /tmp/secure-notes-rendered.yaml; then
  host() { "$K" -n "$NS" get route "$1" -o jsonpath='{.status.ingress[0].host}' 2>/dev/null; }
  for _ in $(seq 1 30); do [ -n "$(host secure-notes)" ] && [ -n "$(host sns-logger)" ] && break; sleep 2; done
  app_host=$(host secure-notes); console_host=$(host sns-logger)
  if [ -n "$console_host" ]; then
    echo "== pointing the console link at https://$console_host"
    "$K" -n "$NS" set env deploy/sns-logger SNS_LOGGER_PUBLIC_URL="https://$console_host" >/dev/null
    "$K" -n "$NS" set env deploy/secure-notes ALERTS_INBOX_URL="https://$console_host" >/dev/null
    "$K" -n "$NS" rollout status deploy/sns-logger --timeout=180s
    "$K" -n "$NS" rollout status deploy/secure-notes --timeout=420s
  fi
  echo
  echo "app:                  https://${app_host:-<route not admitted yet: $K -n $NS get route>}"
  echo "notification console: https://${console_host:-<route not admitted yet>}"
elif grep -q 'nodePort: 30080' /tmp/secure-notes-rendered.yaml; then
  echo
  echo "app:                  http://localhost:${KIND_APP_PORT:-3000}"
  echo "notification console: http://localhost:${KIND_CONSOLE_PORT:-4575}"
fi
