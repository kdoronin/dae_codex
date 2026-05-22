#!/usr/bin/env bash
set -euo pipefail

# Compatibility delegate for older ATDD hook bridges. Completion policy now
# lives in the unified engineer guard.

ATDD_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
ENGINEER_ROOT="${DAE_ENGINEER_ROOT:-}"
if [ -z "$ENGINEER_ROOT" ] && [ -n "$ATDD_ROOT" ] && [ -x "$ATDD_ROOT/../engineer/scripts/dae_guard.py" ]; then
  ENGINEER_ROOT="$(cd "$ATDD_ROOT/../engineer" && pwd)"
fi
if [ -z "$ENGINEER_ROOT" ] && [ -n "$ATDD_ROOT" ]; then
  for candidate in "$ATDD_ROOT"/../../engineer/*; do
    if [ -x "$candidate/scripts/dae_guard.py" ]; then
      ENGINEER_ROOT="$(cd "$candidate" && pwd)"
      break
    fi
  done
fi
if [ -z "$ENGINEER_ROOT" ]; then
  ENGINEER_ROOT="$(cd "$(dirname "$0")/../../../engineer" && pwd)"
fi

exec python3 "$ENGINEER_ROOT/scripts/dae_guard.py" post-tool-use
