#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="${HOME}/.docker/cli-plugins"
PLUGIN_PATH="${PLUGIN_DIR}/docker-compose"
VERSION="v2.36.2"
URL="https://github.com/docker/compose/releases/download/${VERSION}/docker-compose-linux-x86_64"

mkdir -p "${PLUGIN_DIR}"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "${URL}" -o "${PLUGIN_PATH}"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "${PLUGIN_PATH}" "${URL}"
else
  python3 - <<PY
import urllib.request
urllib.request.urlretrieve("${URL}", "${PLUGIN_PATH}")
PY
fi

chmod +x "${PLUGIN_PATH}"
docker compose version
