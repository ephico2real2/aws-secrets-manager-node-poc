#!/usr/bin/env bash
# Zip the app for the CloudFormation stack and upload it to S3.
#   ./scripts/package.sh my-artifacts-bucket [secure-notes/app.zip]
set -euo pipefail
BUCKET="${1:?usage: package.sh <bucket> [key]}"
KEY="${2:-secure-notes/app.zip}"
cd "$(dirname "$0")/.."
rm -f app.zip
zip -qr app.zip backend/package.json backend/package-lock.json backend/src frontend infra/systemd \
  -x '*/node_modules/*' 2>/dev/null || \
zip -qr app.zip backend/package.json backend/src frontend infra/systemd -x '*/node_modules/*'
aws s3 cp app.zip "s3://${BUCKET}/${KEY}" --sse aws:kms
echo "Uploaded s3://${BUCKET}/${KEY}"
