#!/usr/bin/env bash
# Run a shell snippet on the EC2 instance through SSM Run Command (no SSH, no
# open port) and print its output. Exits with the command's status.
#
#   scripts/aws-ssm-run.sh <instance-id> 'systemctl is-active secure-notes'
set -uo pipefail
INSTANCE="${1:?instance id}"
SNIPPET="${2:?commands}"

params=$(jq -cn --arg c "$SNIPPET" '{commands: [$c], executionTimeout: ["300"]}')
cid=$(aws ssm send-command --instance-ids "$INSTANCE" --document-name AWS-RunShellScript \
  --comment "secure-notes ci" --parameters "$params" --query Command.CommandId --output text) || exit 1

# `aws ssm wait command-executed` fails on a non-zero exit; we want the output either way.
for _ in $(seq 1 100); do
  status=$(aws ssm get-command-invocation --command-id "$cid" --instance-id "$INSTANCE" \
    --query Status --output text 2>/dev/null || echo Pending)
  case "$status" in Success|Failed|Cancelled|TimedOut) break ;; esac
  sleep 3
done

aws ssm get-command-invocation --command-id "$cid" --instance-id "$INSTANCE" \
  --query StandardOutputContent --output text
err=$(aws ssm get-command-invocation --command-id "$cid" --instance-id "$INSTANCE" --query StandardErrorContent --output text)
[ -n "$err" ] && [ "$err" != None ] && printf 'stderr:\n%s\n' "$err" >&2
[ "$status" = Success ]
