#!/usr/bin/env bash
# Create the kind cluster (idempotent). Needs Docker and kind (scripts/versions.env pins the version CI uses).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. scripts/versions.env

if kind get clusters 2>/dev/null | grep -qx "$KIND_CLUSTER"; then
  echo "kind cluster '$KIND_CLUSTER' already exists"
else
  kind create cluster --name "$KIND_CLUSTER" --wait 180s
fi
kubectl config use-context "kind-$KIND_CLUSTER" >/dev/null
kubectl get nodes -o wide
