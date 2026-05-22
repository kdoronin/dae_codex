#!/usr/bin/env bash
set -euo pipefail

ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
if [ -z "$ROOT" ]; then
  ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi
exec python3 "$ROOT/scripts/dae_guard.py" post-tool-use
