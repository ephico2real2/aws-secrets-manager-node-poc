#!/usr/bin/env bash
# Prepare a MacBook (Apple silicon or Intel) for the labs, then run the
# preflight. Installs what is missing with Homebrew; changes nothing else.
#
#   scripts/bootstrap/macos.sh                 # Docker Compose and kind, on Docker Desktop
#   scripts/bootstrap/macos.sh --podman        # the same, on Podman Desktop (a smaller VM)
#   scripts/bootstrap/macos.sh --openshift     # also the OpenShift CLI (oc); combines with --podman
#
# What it installs (Homebrew formulae): bash (macOS ships 3.2; the scripts
# need 4.4+), jq, node, kind, kubernetes-cli; with --openshift, openshift-cli.
# The container engine, as a cask if its app is missing:
#   - Docker Desktop (default).
#   - --podman: Podman Desktop and the podman formula, plus the docker and docker-compose
#     formulae if no docker CLI is installed: the lab's scripts call `docker`, which talks to
#     Podman through the machine's API socket (DOCKER_HOST).
# PyYAML for scripts/sync-event-pattern.py, in .tmp/venv (Homebrew's Python refuses
# `pip install --user`, PEP 668), at the version CI uses (scripts/versions.env).
# What stays yours, on purpose:
#   - Homebrew itself (https://brew.sh): its installer needs your password.
#   - The engine's first launch and its memory: Docker Desktop's Settings > Resources, or
#     `podman machine set --memory`. 4 GiB runs Compose and kind; the preflight prints what the VM has.
#   - OpenShift Local (CRC): download it with your Red Hat account from
#     console.redhat.com/openshift/create/local, then `crc setup && crc start`.
#
# Run it from bash 3.2 or later (it is written so macOS's own bash can run it).
set -euo pipefail
cd "$(dirname "$0")/../.."
[ "$(uname -s)" = Darwin ] || { echo "this is $(uname -s): use scripts/bootstrap/linux.sh" >&2; exit 1; }
OPENSHIFT=0; PODMAN=0
for arg in "$@"; do
  case "$arg" in
    --openshift) OPENSHIFT=1 ;;
    --podman) PODMAN=1 ;;
    *) echo "unknown option: $arg (use --podman and/or --openshift)" >&2; exit 2 ;;
  esac
done
# shellcheck disable=SC1091
. scripts/versions.env

if ! command -v brew >/dev/null; then
  for p in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$p" ] && eval "$("$p" shellenv)" && break; done
fi
command -v brew >/dev/null || {
  echo "Homebrew is required: install it from https://brew.sh (it asks for your password), then run this again." >&2
  exit 1
}

formulae="bash jq node kind kubernetes-cli"
[ "$OPENSHIFT" = 1 ] && formulae="$formulae openshift-cli"
if [ "$PODMAN" = 1 ]; then
  formulae="$formulae podman"
  command -v docker >/dev/null || formulae="$formulae docker docker-compose"
fi
missing=""
for f in $formulae; do brew list --formula "$f" >/dev/null 2>&1 || missing="$missing $f"; done
if [ -n "$missing" ]; then echo "== brew install$missing"; brew install $missing; hash -r
else echo "== Homebrew: $formulae already installed"; fi

if [ "$PODMAN" = 1 ]; then
  [ -d "/Applications/Podman Desktop.app" ] || { echo "== brew install --cask podman-desktop"; brew install --cask podman-desktop; }
  if ! podman machine inspect >/dev/null 2>&1; then
    echo "== podman machine init (4 CPUs, 4 GiB, rootless: enough for Compose and kind)"
    podman machine init --cpus 4 --memory 4096
  fi
  if [ "$(podman machine inspect --format '{{.State}}')" != running ]; then
    echo "== podman machine start"; podman machine start
  fi
  sock=$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}')
  export DOCKER_HOST="unix://$sock" KIND_EXPERIMENTAL_PROVIDER=podman
  if ! docker compose version >/dev/null 2>&1; then
    # Homebrew's docker-compose is a CLI plugin; the docker CLI finds it only through this setting.
    echo "docker compose is not found: add \"cliPluginsExtraDirs\": [\"$(brew --prefix)/lib/docker/cli-plugins\"] to ~/.docker/config.json" >&2
  fi
else
  if [ ! -d /Applications/Docker.app ]; then
    echo "== brew install --cask docker-desktop"
    brew install --cask docker-desktop
    echo "Open Docker Desktop once (open -a Docker), accept its terms, then run this again."
    exit 0
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "== starting Docker Desktop"; open -a Docker
    for _ in $(seq 1 120); do docker info >/dev/null 2>&1 && break; sleep 2; done
  fi
fi

if ! .tmp/venv/bin/python3 -c 'import yaml' 2>/dev/null; then
  echo "== PyYAML $PYYAML_VERSION in .tmp/venv (for scripts/sync-event-pattern.py)"
  python3 -m venv .tmp/venv && .tmp/venv/bin/pip install -q "pyyaml==$PYYAML_VERSION"
fi

echo "== the bash your scripts will run: $(command -v bash) ($(bash -c 'echo $BASH_VERSION'))"
echo "   (Homebrew's must come first on PATH; a new Terminal picks it up)"
scripts/preflight.sh compose
scripts/preflight.sh kind
[ "$OPENSHIFT" = 1 ] && scripts/preflight.sh openshift
echo
if [ "$PODMAN" = 1 ]; then
  echo "Next, in each new Terminal (or in your shell profile), point the docker CLI and kind at Podman:"
  # shellcheck disable=SC2016  # printed for the reader to paste, not expanded here
  echo '  export DOCKER_HOST="unix://$(podman machine inspect --format '"'"'{{.ConnectionInfo.PodmanSocket.Path}}'"'"')"'
  echo "  export KIND_EXPERIMENTAL_PROVIDER=podman"
  echo "then: docker compose up --build -d   (or scripts/kind-up.sh; see HANDOVER.md section 11)"
else
  echo "Next: docker compose up --build -d   (or scripts/kind-up.sh; see HANDOVER.md section 11)"
fi
