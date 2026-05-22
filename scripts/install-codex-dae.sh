#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  install-codex-dae.sh [--source OWNER/REPO|PATH|GIT_URL] [--ref REF] [--runtime-enforcement] [--verify]

Environment:
  CODEX_HOME        Codex home directory. Defaults to ~/.codex.
  DAE_CODEX_SOURCE  Marketplace source. Defaults to swingerman/disciplined-agentic-engineering.
  DAE_CODEX_REF     Git ref for Git marketplace sources. Defaults to main.

This installer does not enable danger-full-access, approval bypasses, or unsafe permissions.
USAGE
}

SOURCE="${DAE_CODEX_SOURCE:-swingerman/disciplined-agentic-engineering}"
REF="${DAE_CODEX_REF:-main}"
MARKETPLACE="disciplined-agentic-engineering"
CODEX_HOME="${CODEX_HOME:-"$HOME/.codex"}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_ENFORCEMENT=0
VERIFY=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --source)
      SOURCE="${2:?missing value for --source}"
      shift 2
      ;;
    --ref)
      REF="${2:?missing value for --ref}"
      shift 2
      ;;
    --runtime-enforcement)
      RUNTIME_ENFORCEMENT=1
      shift
      ;;
    --verify)
      VERIFY=1
      RUNTIME_ENFORCEMENT=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

command -v codex >/dev/null 2>&1 || {
  echo "codex CLI is required on PATH" >&2
  exit 127
}

mkdir -p "$CODEX_HOME"

case "$SOURCE" in
  .|/*|~/*|../*|./*)
    codex plugin marketplace add "$SOURCE"
    ;;
  *)
    codex plugin marketplace add "$SOURCE" --ref "$REF"
    ;;
esac

codex plugin add "engineer@$MARKETPLACE"
codex plugin add "atdd@$MARKETPLACE"
codex plugin add "crap-analyzer@$MARKETPLACE"

python3 - "$CODEX_HOME/config.toml" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
text = path.read_text(encoding="utf-8") if path.exists() else ""
lines = text.splitlines()

def ensure_section(lines: list[str], section: str) -> int:
    header = f"[{section}]"
    for index, line in enumerate(lines):
        if line.strip() == header:
            return index
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(header)
    return len(lines) - 1

def section_end(lines: list[str], start: int) -> int:
    index = start + 1
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            break
        index += 1
    return index

def set_bool(lines: list[str], section: str, key: str, value: bool) -> None:
    start = ensure_section(lines, section)
    end = section_end(lines, start)
    prefix = f"{key} ="
    rendered = f"{key} = {'true' if value else 'false'}"
    for index in range(start + 1, end):
        if lines[index].strip().startswith(prefix):
            lines[index] = rendered
            return
    lines.insert(end, rendered)

for feature in ("hooks", "plugin_hooks", "goals"):
    set_bool(lines, "features", feature, True)

path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
PY

ENGINEER_ROOT="$(find "$CODEX_HOME/plugins/cache/$MARKETPLACE/engineer" -mindepth 1 -maxdepth 1 -type d -print 2>/dev/null | sort | tail -n 1)"
if [ -z "$ENGINEER_ROOT" ]; then
  echo "failed to locate installed engineer plugin under $CODEX_HOME/plugins/cache/$MARKETPLACE/engineer" >&2
  exit 1
fi

if [ "$RUNTIME_ENFORCEMENT" -eq 1 ]; then
  DATA_HOME="$CODEX_HOME/dae/data/engineer"
  BRIDGE_HOME="$CODEX_HOME/dae"
  BRIDGE="$BRIDGE_HOME/hook-bridge.py"
  mkdir -p "$BRIDGE_HOME" "$DATA_HOME" "$REPO_ROOT/.dae-project-start-enforcement/logs" "$REPO_ROOT/.dae-project-start-enforcement/reports"
  chmod +x "$ENGINEER_ROOT"/hooks/scripts/dae-*.sh "$ENGINEER_ROOT/scripts/dae_guard.py"

  python3 - "$BRIDGE" "$ENGINEER_ROOT" "$DATA_HOME" <<'PY'
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

bridge = Path(sys.argv[1]).expanduser()
engineer_root = Path(sys.argv[2]).expanduser().resolve()
data_home = Path(sys.argv[3]).expanduser().resolve()
bridge.parent.mkdir(parents=True, exist_ok=True)
(bridge.parent / "installed-plugin-root.json").write_text(
    json.dumps({"engineer_root": str(engineer_root), "plugin_data": str(data_home)}, indent=2) + "\n",
    encoding="utf-8",
)
bridge.write_text(
    """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

def codex_home() -> Path:
    if os.environ.get("CODEX_HOME"):
        return Path(os.environ["CODEX_HOME"]).expanduser().resolve()
    return Path(__file__).resolve().parent.parent

def configured_root() -> Path:
    for key in ("DAE_PLUGIN_ROOT", "CODEX_DAE_PLUGIN_ROOT", "PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
        value = os.environ.get(key)
        if value and (Path(value).expanduser() / "scripts" / "dae_guard.py").exists():
            return Path(value).expanduser().resolve()
    config = codex_home() / "dae" / "installed-plugin-root.json"
    if config.exists():
        data = json.loads(config.read_text(encoding="utf-8"))
        root = Path(data.get("engineer_root", "")).expanduser()
        if (root / "scripts" / "dae_guard.py").exists():
            return root.resolve()
    raise SystemExit("DAE hook bridge cannot locate engineer plugin root; run install-codex-dae.sh --runtime-enforcement --verify")

def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: hook-bridge.py <dae_guard_subcommand>")
    root = configured_root()
    env = os.environ.copy()
    env.setdefault("PLUGIN_ROOT", str(root))
    config = codex_home() / "dae" / "installed-plugin-root.json"
    if config.exists():
        data = json.loads(config.read_text(encoding="utf-8"))
        if data.get("plugin_data"):
            env.setdefault("PLUGIN_DATA", data["plugin_data"])
    return subprocess.run(["python3", str(root / "scripts" / "dae_guard.py"), sys.argv[1]], env=env).returncode

if __name__ == "__main__":
    raise SystemExit(main())
""",
    encoding="utf-8",
)
bridge.chmod(0o755)
PY

  python3 - "$CODEX_HOME/hooks.json" "$BRIDGE" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

hooks_path = Path(sys.argv[1]).expanduser()
bridge = Path(sys.argv[2]).expanduser()
managed_markers = (
    "dae/hook-bridge.py",
    "dae-codex/hooks/atdd/check-specs-exist.sh",
    "dae-codex/hooks/atdd/stop-reminder.sh",
    "disciplined-agentic-engineering/atdd/",
    "DAE_HOOK_AUDIT_LOG=",
)

if hooks_path.exists():
    data = json.loads(hooks_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{hooks_path} must contain a JSON object")
else:
    data = {"description": "Codex lifecycle hooks"}

hooks = data.setdefault("hooks", {})
if not isinstance(hooks, dict):
    raise SystemExit(f"{hooks_path}: top-level hooks must be an object")

def command_is_dae_managed(group: object) -> bool:
    if not isinstance(group, dict):
        return False
    for hook in group.get("hooks", []):
        command = str(hook.get("command", "")) if isinstance(hook, dict) else ""
        if any(marker in command for marker in managed_markers):
            return True
    return False

def replace_event(event: str, subcommand: str, matcher: str | None = None) -> None:
    groups = hooks.get(event, [])
    if not isinstance(groups, list):
        raise SystemExit(f"{hooks_path}: hooks.{event} must be a list")
    groups = [group for group in groups if not command_is_dae_managed(group)]
    command = f'python3 "{bridge}" {subcommand}'
    group = {
        "hooks": [{
            "type": "command",
            "command": command,
            "timeout": 30,
            "statusMessage": f"DAE runtime guard: {subcommand}",
        }],
    }
    if matcher is not None:
        group["matcher"] = matcher
    groups.append(group)
    hooks[event] = groups

replace_event("SessionStart", "session-start", "startup|resume|clear")
replace_event("UserPromptSubmit", "user-prompt-submit")
replace_event("PreToolUse", "pre-tool-use", "Bash|apply_patch|Edit|Write|mcp__.*")
replace_event("PostToolUse", "post-tool-use", "Bash|apply_patch|Edit|Write|mcp__.*")
replace_event("PermissionRequest", "permission-request", "Bash|apply_patch|Edit|Write|mcp__.*")
replace_event("Stop", "stop")

data["description"] = (
    "Codex lifecycle hooks. Includes DAE runtime enforcement installed by "
    "install-codex-dae.sh --runtime-enforcement."
)
hooks_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

  DOCTOR_LOG="$REPO_ROOT/.dae-project-start-enforcement/logs/doctor-after-init.json"
  if PLUGIN_ROOT="$ENGINEER_ROOT" PLUGIN_DATA="$DATA_HOME" CODEX_PROJECT_DIR="$REPO_ROOT" python3 "$ENGINEER_ROOT/scripts/dae_guard.py" doctor > "$DOCTOR_LOG"; then
    DOCTOR_STATUS="PASS"
  else
    DOCTOR_STATUS="FAIL"
  fi

  PROBE_STATUS="SKIPPED"
  if [ "$VERIFY" -eq 1 ]; then
    if python3 "$REPO_ROOT/plugins/engineer/scripts/project_start_hook_probe.py" \
      --out ".dae-project-start-enforcement" \
      > "$REPO_ROOT/.dae-project-start-enforcement/reports/hook-probe-results.json"; then
      PROBE_STATUS="PASS"
    else
      PROBE_STATUS="FAIL"
    fi
  fi

  cat > "$REPO_ROOT/.dae-project-start-enforcement/logs/init-runtime-enforcement.md" <<EOF
# DAE runtime enforcement init

- engineer_root: \`$ENGINEER_ROOT\`
- bridge: \`$BRIDGE\`
- hooks_config: \`$CODEX_HOME/hooks.json\`
- plugin_data: \`$DATA_HOME\`
- doctor: \`$DOCTOR_STATUS\`
- synthetic_probes: \`$PROBE_STATUS\`

Review and trust non-managed hooks in Codex with \`/hooks\` when prompted.
EOF

  if [ "$DOCTOR_STATUS" != "PASS" ]; then
    echo "dae_guard.py doctor failed; see $DOCTOR_LOG" >&2
    exit 1
  fi
  if [ "$VERIFY" -eq 1 ] && [ "$PROBE_STATUS" != "PASS" ]; then
    echo "runtime hook probes failed; see $REPO_ROOT/.dae-project-start-enforcement/reports/hook-probe-results.json" >&2
    exit 1
  fi
fi

cat <<EOF
DAE Codex plugins installed and enabled from: $SOURCE
Marketplace: $MARKETPLACE
Engineer plugin root: $ENGINEER_ROOT
Runtime enforcement: $([ "$RUNTIME_ENFORCEMENT" -eq 1 ] && echo enabled || echo not initialized)
Hook bridge: $CODEX_HOME/hooks.json

Start Codex in a project with:
  codex --sandbox workspace-write

Verify with:
  codex plugin list --marketplace $MARKETPLACE
  python3 "$ENGINEER_ROOT/scripts/dae_guard.py" doctor
EOF
