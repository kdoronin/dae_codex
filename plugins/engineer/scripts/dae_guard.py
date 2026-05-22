#!/usr/bin/env python3
"""Runtime guard for Disciplined Agentic Engineering Codex hooks.

The guard is intentionally stdlib-only. Hook wrappers pass one lifecycle event
on stdin; this script loads the DAE contract, inspects project state, emits a
Codex hook response, and appends JSONL audit evidence.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

KNOWN_EVENTS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PermissionRequest",
    "Stop",
}
SUBCOMMAND_EVENTS = {
    "session-start": "SessionStart",
    "user-prompt-submit": "UserPromptSubmit",
    "pre-tool-use": "PreToolUse",
    "post-tool-use": "PostToolUse",
    "permission-request": "PermissionRequest",
    "stop": "Stop",
}
VALID_MODES = {
    "hard_gate",
    "advisory_guard",
    "audit_only",
    "skill_gate",
    "ci_release_gate",
    "platform_limit",
}
REQUIRED_SUBCOMMANDS = {
    "session-start",
    "user-prompt-submit",
    "pre-tool-use",
    "post-tool-use",
    "permission-request",
    "stop",
    "doctor",
    "state",
    "validate-contract",
    "quality-config",
    "validate-quality-config",
    "quality-status",
    "quality-mark-dirty",
    "quality-required-evidence",
    "quality-validate-evidence",
    "quality-record-evidence",
    "quality-verify",
    "quality-reset-dirty",
    "quality-doctor",
}
REQUIRED_RULE_IDS = {
    "dae.session_context_loaded",
    "dae.pipeline_order",
    "dae.feature_charter_required",
    "dae.acceptance_criteria_required",
    "dae.acceptance_criteria_human_approved",
    "dae.gherkin_spec_required",
    "dae.spec_leakage_forbidden",
    "dae.plan_required_before_implementation",
    "dae.plan_human_approved",
    "dae.source_write_requires_gates",
    "dae.generated_acceptance_tests_immutable",
    "dae.two_test_streams_required",
    "dae.acceptance_tests_green",
    "dae.unit_tests_green",
    "dae.progress_breadcrumb_required",
    "dae.handoff_required",
    "dae.branch_hygiene_required",
    "dae.mutation_workflow_required_when_configured",
    "dae.crap_analysis_required_when_configured",
    "dae.architecture_check_required_when_configured",
    "dae.refine_review_required_when_configured",
    "dae.duplicate_detection_required_when_configured",
    "dae.test_impact_required_when_configured",
    "dae.unsafe_permission_denied",
    "dae.destructive_command_denied",
    "dae.out_of_workspace_write_denied",
    "dae.audit_log_required",
    "dae.docs_do_not_overpromise_enforcement",
}

IMPLEMENTATION_PROMPT_RE = re.compile(
    r"\b(implement|build|add|create|write|code|patch|fix|refactor|измен|"
    r"реализ|добав|почин|напиш|сделай)\b",
    re.IGNORECASE,
)
NEW_PROJECT_PROMPT_RE = re.compile(
    r"(from\s+scratch|from\s+zero|new\s+(project|app|application|saas)|"
    r"create\s+(a\s+)?new|build\s+(me\s+)?(a\s+)?(?:todo|crm|saas|app|project)|"
    r"с\s+нуля|сделай\s+с\s+нуля|нов(ый|ое|ую)\s+(проект|прилож|crm|сервис)|"
    r"создай\s+(нов|с\s+нуля))",
    re.IGNORECASE,
)
PLANNING_ONLY_PROMPT_RE = re.compile(
    r"(only\s+(a\s+)?plan|planning\s+only|do\s+not\s+write\s+code|без\s+кода|только\s+план)",
    re.IGNORECASE,
)
APPROVAL_PROMPT_RE = re.compile(
    r"(i\s+approve|approved|approve\s+the\s+plan|план\s+подтвержд|подтверждаю|одобряю)",
    re.IGNORECASE,
)
BYPASS_PROMPT_RE = re.compile(
    r"(ignore\s+dae|skip\s+(spec|test|plan|approval)|just\s+implement|"
    r"no\s+spec|approve\s+everything|bypass|danger[- ]full|yolo|"
    r"без\s+(спек|тест|план)|игнорируй\s+dae)",
    re.IGNORECASE,
)
FINALIZE_PROMPT_RE = re.compile(
    r"\b(done|complete|ship|shipping|release|publish|merge|commit|push|finalize|"
    r"готово|закончи|заверши|релиз|запуш|коммит)\b",
    re.IGNORECASE,
)
WORKFLOW_PROMPT_RE = re.compile(
    r"\b(feature-init|discover[- ]acs?|acceptance criteria|gherkin|spec|"
    r"plan|reorient|onboard|handoff|progress|arch-check|crap|mutation|"
    r"atdd|приемочн|критери|план|спек)\b",
    re.IGNORECASE,
)
RELEASE_COMMAND_RE = re.compile(
    r"\b(git\s+commit|git\s+push|git\s+merge|git\s+rebase|gh\s+pr\s+merge|"
    r"npm\s+publish|pnpm\s+publish|yarn\s+npm\s+publish|twine\s+upload|"
    r"docker\s+push|kubectl\s+apply|helm\s+(?:upgrade|install)|"
    r"vercel\s+deploy|netlify\s+deploy|fly\s+deploy|railway\s+up|"
    r"release|publish|deploy)\b",
    re.IGNORECASE,
)
QUALITY_BYPASS_RE = re.compile(
    r"(quality[- ]gate|crap|mutation|acceptance|unit).{0,40}"
    r"(bypass|skip|ignore|disable|turn\s+off|remove|force)",
    re.IGNORECASE,
)
SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".swift",
    ".m",
    ".mm",
    ".scala",
    ".sh",
}
PROJECT_START_STATES = [
    "NO_DAE_STATE",
    "PROJECT_INTAKE",
    "CHARTER_DRAFTED",
    "CHARTER_APPROVED",
    "ACS_DRAFTED",
    "SPEC_DRAFTED",
    "SPEC_APPROVED",
    "PLAN_DRAFTED",
    "PLAN_APPROVED",
    "IMPLEMENTATION_ALLOWED",
    "VERIFYING",
    "DONE",
]
PROJECT_START_FEATURE_ID = "000-project-start"
SAFE_WRITE_PREFIXES = (
    ".dae-runtime-enforcement/",
    ".dae-project-start-enforcement/",
    ".engineer/",
    ".dae/",
    "features/",
    "docs/dae/",
    "README",
    "AGENTS",
)
QUALITY_GATE_NAMES = (
    "acceptance",
    "unit",
    "crap",
    "arch",
    "refine",
    "branch_hygiene",
    "progress",
    "handoff",
    "duplicate_detection",
    "test_impact",
    "generated_acceptance_immutability",
    "mutation",
)
QUALITY_EVIDENCE_LABELS = {
    "acceptance": "acceptance_stream",
    "unit": "unit_stream",
    "crap": "crap_analysis",
    "arch": "architecture_check",
    "refine": "refine_review",
    "branch_hygiene": "branch_hygiene",
    "progress": "progress_breadcrumb",
    "handoff": "durable_handoff",
    "duplicate_detection": "duplicate_detection",
    "test_impact": "test_impact",
    "generated_acceptance_immutability": "generated_acceptance_immutability",
    "mutation": "mutation_workflow",
}
QUALITY_LEGACY_EVIDENCE_FILES = {
    "acceptance": ("acceptance-tests.json",),
    "unit": ("unit-tests.json",),
    "crap": ("crap.json",),
    "arch": ("architecture.json",),
}
ALLOWED_BEFORE_PLAN_APPROVED = (
    ".engineer/**",
    ".dae/**",
    "CHARTER.md",
    "PROJECT_CHARTER.md",
    "features/**/feature.md",
    "features/**/acs.md",
    "features/**/acceptance-criteria.md",
    "features/**/acceptance_criteria.md",
    "features/**/spec.md",
    "features/**/plan.md",
    "features/**/progress.md",
    "features/**/handoffs/*.md",
    "docs/dae/**",
)
BLOCKED_BEFORE_PLAN_APPROVED = (
    "src/**",
    "app/**",
    "lib/**",
    "server/**",
    "client/**",
    "web/**",
    "api/**",
    "components/**",
    "pages/**",
    "routes/**",
    "migrations/**",
    "tests/**",
    "__tests__/**",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "Dockerfile",
    "docker-compose*.yml",
    "Makefile",
    "*.go",
    "*.rs",
    "*.py",
    "*.ts",
    "*.tsx",
    "*.js",
    "*.jsx",
    "*.java",
    "*.kt",
    "*.cs",
    "*.php",
    "*.rb",
)
WRITE_PATTERNS = [
    re.compile(r"^\*\*\* (?:Add|Update|Delete) File:\s*(.+)$", re.MULTILINE),
    re.compile(r"\b(?:cat|tee)\b.*?(?:>|>>)\s+([^\s;|&]+)"),
    re.compile(r"\b(?:python3?|node|ruby|perl)\b.*?\bopen\(['\"]([^'\"]+)['\"]\s*,\s*['\"][wa]"),
    re.compile(r"\b(?:touch|truncate)\s+([^\s;|&]+)"),
]
SCAFFOLD_COMMAND_RE = re.compile(
    r"\b(npm\s+init|npm\s+create|npx\s+create-[\w.-]+|pnpm\s+create|"
    r"yarn\s+create|poetry\s+init|cargo\s+new|go\s+mod\s+init|rails\s+new|"
    r"django-admin\s+startproject|uv\s+init)\b",
    re.IGNORECASE,
)
Mkdir_SOURCE_RE = re.compile(
    r"\bmkdir\s+(?:-[^\s]+\s+)*(?P<paths>(?:src|app|lib|server|client|web|api|components|pages|routes|tests)(?:\s+|$)[^\n;]*)",
    re.IGNORECASE,
)
DESTRUCTIVE_RE = re.compile(
    r"\b(rm\s+-[^\n;]*(?:r|f)|git\s+reset\s+--hard|git\s+clean\s+-[^\n;]*[fdx]|"
    r"mkfs|dd\s+if=|chmod\s+-R\s+777|chown\s+-R)\b",
    re.IGNORECASE,
)
UNSAFE_PERMISSION_RE = re.compile(
    r"\b(danger-full-access|dangerously-bypass|approval\s*bypass|bypass\s+permissions|sudo\b|"
    r"chmod\s+-R\s+777|rm\s+-rf\s+/|outside\s+workspace|full\s+disk\s+access)\b",
    re.IGNORECASE,
)
SPEC_LEAKAGE_RE = re.compile(
    r"\b(class|function|method|private|repository|controller|service|database|"
    r"table|column|query|endpoint|POST|GET|PUT|DELETE|PATCH|/api/|def\s+|"
    r"[A-Za-z0-9]+Service|[A-Za-z0-9]+Repository|_[a-zA-Z0-9_]+)\b"
)


def now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def script_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"_invalid_json": str(exc), "_raw": raw}
    return data if isinstance(data, dict) else {"_raw": data}


def discover_project_root(event: dict[str, Any]) -> Path:
    candidates = [
        event.get("cwd"),
        os.environ.get("CODEX_PROJECT_DIR"),
        os.environ.get("CLAUDE_PROJECT_DIR"),
        os.getcwd(),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(str(candidate)).expanduser().resolve()
        current = path if path.is_dir() else path.parent
        for parent in [current, *current.parents]:
            if (parent / ".git").exists():
                return parent
            if (parent / "AGENTS.md").exists() and ((parent / "features").exists() or (parent / ".engineer").exists()):
                return parent
        return current
    return Path.cwd().resolve()


def project_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def plugin_data_root(project_root: Path) -> Path:
    data = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if data:
        return Path(data).expanduser().resolve() / "dae-runtime"
    return project_root / ".dae-project-start-enforcement" / "audit"


def load_contract() -> dict[str, Any]:
    path = script_root() / "guardrails" / "dae-contract.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def rule_mode(rule_id: str, event_name: str) -> str:
    try:
        rules = load_contract().get("rules", [])
    except Exception:
        return "audit_only"
    for rule in rules:
        if rule.get("id") == rule_id:
            mode = rule.get("enforcement_mode") or {}
            return str(mode.get(event_name) or mode.get("docs") or "audit_only")
    return "audit_only"


def write_audit(
    event: dict[str, Any],
    project_root: Path,
    rule_id: str,
    decision: str,
    message: str,
    missing: list[str] | None = None,
    tool_name: str | None = None,
) -> None:
    audit_dir = plugin_data_root(project_root)
    audit_dir.mkdir(parents=True, exist_ok=True)
    event_name = str(event.get("hook_event_name") or hook_event_from_command() or "")
    record = {
        "schema_version": "1.0",
        "timestamp": now_iso(),
        "event": event_name,
        "rule_id": rule_id,
        "decision": decision,
        "enforcement_mode": rule_mode(rule_id, event_name),
        "project_root": str(project_root),
        "feature_id": None,
        "missing_evidence": missing or [],
        "message": message,
        "tool_name": tool_name or event.get("tool_name"),
        "session_id": event.get("session_id"),
        "turn_id": event.get("turn_id"),
    }
    state = inspect_state(project_root)
    record["feature_id"] = state.get("active_feature")
    with (audit_dir / "audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def hook_event_from_command() -> str:
    if len(sys.argv) > 1 and sys.argv[1] in SUBCOMMAND_EVENTS:
        return SUBCOMMAND_EVENTS[sys.argv[1]]
    name = Path(sys.argv[0]).name
    if "session-start" in name:
        return "SessionStart"
    if "user-prompt-submit" in name:
        return "UserPromptSubmit"
    if "pre-tool-use" in name:
        return "PreToolUse"
    if "post-tool-use" in name:
        return "PostToolUse"
    if "permission-request" in name:
        return "PermissionRequest"
    if name.endswith("stop"):
        return "Stop"
    return ""


def emit_json(obj: dict[str, Any]) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")


def hook_specific(event_name: str, **values: Any) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event_name, **values}}


def emit_context(message: str) -> None:
    event_name = hook_event_from_command()
    if event_name in {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse"}:
        emit_json(hook_specific(event_name, additionalContext=message))
    else:
        print(f"DAE hook context requested for unsupported event {event_name or 'unknown'}: {message}", file=sys.stderr)


def emit_allow_context(message: str) -> None:
    emit_context(message)


def emit_block(message: str) -> None:
    event_name = hook_event_from_command()
    if event_name in {"UserPromptSubmit", "PostToolUse"}:
        emit_json(
            {
                "decision": "block",
                "reason": message,
                **hook_specific(event_name, additionalContext=message),
            }
        )
    elif event_name == "PreToolUse":
        emit_pre_tool_deny(message)
    elif event_name == "Stop":
        emit_stop_continue(message)
    else:
        emit_json({"decision": "block", "reason": message})


def emit_pre_tool_deny(message: str) -> None:
    emit_json(
        hook_specific(
            "PreToolUse",
            permissionDecision="deny",
            permissionDecisionReason=message,
            additionalContext=message,
        )
    )


def emit_permission_deny(message: str) -> None:
    emit_json(
        hook_specific(
            "PermissionRequest",
            decision={
                "behavior": "deny",
                "message": message,
            },
        )
    )


def emit_deny(message: str) -> None:
    event_name = hook_event_from_command()
    if event_name == "PermissionRequest":
        emit_permission_deny(message)
    elif event_name == "PreToolUse":
        emit_pre_tool_deny(message)
    else:
        emit_block(message)


def emit_stop_continue(message: str) -> None:
    emit_json({"decision": "block", "reason": message})


def emit_continue(message: str) -> None:
    emit_stop_continue(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def quality_default_config_path() -> Path:
    return script_root() / "guardrails" / "dae-quality-gates.default.json"


def quality_config_candidates(project_root: Path) -> list[Path]:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    paths = [
        quality_default_config_path(),
        codex_home / "dae" / "quality-gates.json",
        project_root / ".dae" / "quality-gates.json",
        project_root / ".engineer" / "dae-quality-gates.json",
    ]
    env = os.environ.get("DAE_QUALITY_CONFIG")
    if env:
        paths.append(Path(env).expanduser().resolve())
    return paths


def load_quality_config(project_root: Path) -> tuple[dict[str, Any], list[str], list[str]]:
    config: dict[str, Any] = {}
    loaded: list[str] = []
    errors: list[str] = []
    for path in quality_config_candidates(project_root):
        if not path.exists():
            continue
        data = read_json(path)
        if not data:
            errors.append(f"{path}: invalid or empty JSON object")
            continue
        config = deep_merge(config, data)
        loaded.append(str(path))
    if not config:
        errors.append(f"{quality_default_config_path()}: default quality config missing")
    validation_errors = validate_quality_config_data(config, loaded)
    return config, loaded, errors + validation_errors


def default_quality_gate_modes() -> dict[str, str]:
    data = read_json(quality_default_config_path())
    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    return {str(name): str(value.get("mode")) for name, value in gates.items() if isinstance(value, dict)}


def validate_quality_config_data(config: dict[str, Any], loaded: list[str] | None = None) -> list[str]:
    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("quality config schema_version must be 1")
    gates = config.get("gates")
    if not isinstance(gates, dict) or not gates:
        errors.append("quality config gates must be a non-empty object")
        return errors
    default_modes = default_quality_gate_modes()
    for gate, data in gates.items():
        if gate not in QUALITY_GATE_NAMES:
            errors.append(f"unknown quality gate {gate}")
        if not isinstance(data, dict):
            errors.append(f"gate {gate} must be an object")
            continue
        mode = data.get("mode")
        if mode not in {"required", "warn", "off", "conditional"}:
            errors.append(f"gate {gate} has invalid mode {mode!r}")
            continue
        if default_modes.get(str(gate)) == "required" and mode in {"warn", "off"}:
            required_fields = ["justification", "scope", "approved_by", "approved_at"]
            missing = [field for field in required_fields if not str(data.get(field) or "").strip()]
            if not str(data.get("expires_at") or "").strip() and not str(data.get("no_expiry_reason") or "").strip():
                missing.append("expires_at_or_no_expiry_reason")
            if missing:
                errors.append(f"gate {gate} relaxation to {mode} missing audit fields: {', '.join(missing)}")
        if gate == "crap":
            thresholds = data.get("thresholds")
            if not isinstance(thresholds, dict):
                errors.append("crap gate thresholds must be an object")
            else:
                for key in ("max_crap_score", "warn_crap_score", "missing_coverage_policy", "max_high_risk_findings"):
                    if key not in thresholds:
                        errors.append(f"crap gate missing thresholds.{key}")
    return errors


def quality_state_path(project_root: Path) -> Path:
    return project_root / ".engineer" / "quality-state.json"


def quality_audit_path(project_root: Path) -> Path:
    return project_root / ".engineer" / "quality-gate-audit.jsonl"


def load_quality_state(project_root: Path) -> dict[str, Any]:
    state = read_json(quality_state_path(project_root))
    return state if state else {"version": 1, "quality_dirty": False, "changed_files": [], "required_evidence": []}


def write_quality_state(project_root: Path, state: dict[str, Any]) -> None:
    path = quality_state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["version"] = 1
    state["updated_at"] = now_iso()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_quality_audit(project_root: Path, action: str, details: dict[str, Any]) -> None:
    path = quality_audit_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"schema_version": 1, "timestamp": now_iso(), "action": action, **details}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def active_feature_path(project_root: Path, state: dict[str, Any] | None = None) -> Path | None:
    inspected = state or inspect_state(project_root)
    feature_dir = inspected.get("feature_dir")
    if isinstance(feature_dir, str) and feature_dir:
        path = Path(feature_dir)
        return path if path.is_absolute() else project_root / path
    active = inspected.get("active_feature")
    if isinstance(active, str) and active:
        candidate = project_root / "features" / active
        if candidate.exists():
            return candidate
    return latest_feature_dir(project_root)


def quality_evidence_dir(project_root: Path, feature_dir: Path | None) -> Path:
    if feature_dir:
        return feature_dir / "evidence" / "quality"
    return project_root / ".engineer" / "evidence" / "quality"


def quality_evidence_candidates(project_root: Path, feature_dir: Path | None, gate: str, config: dict[str, Any]) -> list[Path]:
    gates = config.get("gates") if isinstance(config.get("gates"), dict) else {}
    gate_config = gates.get(gate) if isinstance(gates.get(gate), dict) else {}
    filename = str(gate_config.get("evidence") or f"{gate}.json")
    candidates = [quality_evidence_dir(project_root, feature_dir) / filename]
    if feature_dir:
        for legacy in QUALITY_LEGACY_EVIDENCE_FILES.get(gate, (f"{gate}.json",)):
            candidates.append(feature_dir / "evidence" / legacy)
    return list(dict.fromkeys(candidates))


def parse_iso(value: Any) -> _dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return _dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None


def crap_triggers_mutation(crap_data: dict[str, Any], config: dict[str, Any]) -> bool:
    gates = config.get("gates") if isinstance(config.get("gates"), dict) else {}
    mutation = gates.get("mutation") if isinstance(gates.get("mutation"), dict) else {}
    required_when = mutation.get("required_when") if isinstance(mutation.get("required_when"), dict) else {}
    thresholds = (gates.get("crap") or {}).get("thresholds", {}) if isinstance(gates.get("crap"), dict) else {}
    warn_score = float(required_when.get("crap_score_gte") or thresholds.get("warn_crap_score") or 20)
    high_risk = int(required_when.get("high_risk_findings_gte") or 1)
    summary = crap_data.get("summary") if isinstance(crap_data.get("summary"), dict) else {}
    try:
        max_score = float(summary.get("max_crap_score") or 0)
    except (TypeError, ValueError):
        max_score = 0
    try:
        findings = int(summary.get("high_risk_findings") or 0)
    except (TypeError, ValueError):
        findings = 0
    return str(crap_data.get("status") or "").upper() == "WARN" or max_score >= warn_score or findings >= high_risk


def quality_required_gates(config: dict[str, Any], project_root: Path, feature_dir: Path | None, dirty: bool = True) -> list[str]:
    if not dirty:
        return []
    gates = config.get("gates") if isinstance(config.get("gates"), dict) else {}
    required: list[str] = []
    for gate in QUALITY_GATE_NAMES:
        data = gates.get(gate)
        if not isinstance(data, dict):
            continue
        mode = data.get("mode")
        if mode == "required":
            required.append(gate)
    mutation = gates.get("mutation") if isinstance(gates.get("mutation"), dict) else {}
    if mutation.get("mode") == "conditional" and "mutation" not in required:
        if "hardening" in str(read_json(project_root / ".engineer" / "dae-state.json").get("checkpoint") or "").lower():
            required.append("mutation")
        crap_path = next((p for p in quality_evidence_candidates(project_root, feature_dir, "crap", config) if p.exists()), None)
        if crap_path and crap_triggers_mutation(read_json(crap_path), config):
            required.append("mutation")
    return required


def quality_statuses(config: dict[str, Any], project_root: Path, feature_dir: Path | None, quality_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    dirty_since = parse_iso(quality_state.get("dirty_since"))
    required = quality_state.get("required_evidence") if isinstance(quality_state.get("required_evidence"), list) else []
    results: dict[str, dict[str, Any]] = {}
    for gate in required:
        paths = quality_evidence_candidates(project_root, feature_dir, str(gate), config)
        path = next((p for p in paths if p.exists()), None)
        if not path:
            results[str(gate)] = {"status": "MISSING", "evidence": None, "errors": ["missing evidence"]}
            continue
        data = read_json(path)
        errors = validate_quality_evidence_data(str(gate), data, config, dirty_since)
        status = str(data.get("status") or "MISSING").upper()
        results[str(gate)] = {
            "status": status if not errors else "FAIL",
            "evidence": project_rel(path, project_root),
            "errors": errors,
        }
    return results


def validate_quality_evidence_data(
    gate: str,
    data: dict[str, Any],
    config: dict[str, Any],
    dirty_since: _dt.datetime | None = None,
) -> list[str]:
    errors: list[str] = []
    for key in ("schema_version", "gate", "status", "generated_at", "feature", "changed_files"):
        if key not in data:
            errors.append(f"missing {key}")
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("gate") != gate:
        errors.append(f"gate must be {gate}")
    if str(data.get("status") or "").upper() != "PASS":
        errors.append(f"required gate {gate} needs PASS status, got {data.get('status')!r}")
    if not isinstance(data.get("changed_files"), list):
        errors.append("changed_files must be a list")
    generated_at = parse_iso(data.get("generated_at"))
    if dirty_since and generated_at and generated_at < dirty_since:
        errors.append("evidence is stale: generated_at is older than dirty_since")
    if gate == "crap":
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        thresholds = data.get("thresholds") if isinstance(data.get("thresholds"), dict) else {}
        gate_cfg = ((config.get("gates") or {}).get("crap") or {}) if isinstance(config.get("gates"), dict) else {}
        default_thresholds = gate_cfg.get("thresholds") if isinstance(gate_cfg.get("thresholds"), dict) else {}
        max_allowed = float(thresholds.get("max_crap_score") or default_thresholds.get("max_crap_score") or 30)
        max_high_risk = int(thresholds.get("max_high_risk_findings") or default_thresholds.get("max_high_risk_findings") or 0)
        try:
            max_score = float(summary.get("max_crap_score"))
        except (TypeError, ValueError):
            errors.append("crap evidence missing numeric summary.max_crap_score")
            max_score = 0
        try:
            high_risk = int(summary.get("high_risk_findings") or 0)
        except (TypeError, ValueError):
            errors.append("crap evidence has invalid summary.high_risk_findings")
            high_risk = 0
        if max_score >= max_allowed:
            errors.append(f"max CRAP score {max_score} exceeds threshold {max_allowed}")
        if high_risk > max_high_risk:
            errors.append(f"high-risk findings {high_risk} exceeds threshold {max_high_risk}")
        coverage_required = bool(default_thresholds.get("coverage_required_for_pass", True))
        missing_policy = str(thresholds.get("missing_coverage_policy") or default_thresholds.get("missing_coverage_policy") or "")
        if coverage_required and not data.get("coverage_source") and "allow" not in missing_policy:
            errors.append("strict CRAP gate requires explicit coverage_source or audited coverage relaxation")
    return errors


def mark_quality_dirty(project_root: Path, paths: list[str], reason: str, event: dict[str, Any] | None = None) -> dict[str, Any]:
    inspected = inspect_state(project_root)
    feature_dir = active_feature_path(project_root, inspected)
    config, loaded, errors = load_quality_config(project_root)
    state = load_quality_state(project_root)
    changed = state.get("changed_files") if isinstance(state.get("changed_files"), list) else []
    for path in paths:
        rel = project_rel((project_root / path) if not Path(path).is_absolute() else Path(path), project_root)
        if rel not in changed:
            changed.append(rel)
    if not state.get("quality_dirty"):
        state["dirty_since"] = now_iso()
    state["quality_dirty"] = True
    state["dirty_reason"] = reason
    state["active_feature"] = inspected.get("active_feature")
    state["changed_files"] = changed
    state["config_profile"] = config.get("profile", "strict")
    state["config_files"] = loaded
    state["config_errors"] = errors
    state["required_evidence"] = quality_required_gates(config, project_root, feature_dir, True)
    state["last_summary"] = None
    write_quality_state(project_root, state)
    append_quality_audit(
        project_root,
        "quality_mark_dirty",
        {
            "reason": reason,
            "changed_files": changed,
            "required_evidence": state["required_evidence"],
            "hook_event_name": (event or {}).get("hook_event_name"),
        },
    )
    return state


def effective_quality_status(project_root: Path) -> dict[str, Any]:
    inspected = inspect_state(project_root)
    feature_dir = active_feature_path(project_root, inspected)
    config, loaded, errors = load_quality_config(project_root)
    state = load_quality_state(project_root)
    state_exists = quality_state_path(project_root).exists()
    dirty = bool(state.get("quality_dirty") or (inspected.get("implementation_started") and not state_exists))
    required = quality_required_gates(config, project_root, feature_dir, dirty)
    state_required = state.get("required_evidence") if isinstance(state.get("required_evidence"), list) else []
    for gate in state_required:
        if gate in QUALITY_GATE_NAMES and gate not in required:
            required.append(gate)
    legacy_required = inspected.get("required_evidence") if isinstance(inspected.get("required_evidence"), dict) else {}
    for gate, enabled in legacy_required.items():
        if enabled and gate in QUALITY_GATE_NAMES and gate not in required:
            required.append(gate)
    if dirty and state.get("required_evidence") != required:
        state["required_evidence"] = required
        state["config_profile"] = config.get("profile", "strict")
        state["config_files"] = loaded
        if state.get("quality_dirty"):
            write_quality_state(project_root, state)
    results = quality_statuses(config, project_root, feature_dir, state)
    blocking = [gate for gate, result in results.items() if result.get("status") != "PASS"]
    relaxed = []
    gates = config.get("gates") if isinstance(config.get("gates"), dict) else {}
    for gate, data in gates.items():
        if isinstance(data, dict) and data.get("mode") in {"warn", "off"}:
            relaxed.append({"gate": gate, "mode": data.get("mode"), "scope": data.get("scope"), "justification": data.get("justification")})
    return {
        "schema_version": 1,
        "status": "PASS" if not errors and not blocking else "FAIL",
        "profile": config.get("profile", "strict"),
        "active_feature": inspected.get("active_feature"),
        "feature_dir": str(feature_dir) if feature_dir else None,
        "quality_dirty": dirty,
        "changed_files": state.get("changed_files") if isinstance(state.get("changed_files"), list) else [],
        "required_gates": required,
        "gate_results": results,
        "blocking_gates": blocking,
        "config_files": loaded,
        "config_errors": errors,
        "relaxed_gates": relaxed,
        "generated_at": now_iso(),
    }


def read_approvals(project_root: Path) -> list[dict[str, Any]]:
    path = project_root / ".engineer" / "approvals.jsonl"
    approvals: list[dict[str, Any]] = []
    if not path.exists():
        return approvals
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            approvals.append(data)
    return approvals


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def approval_event_matches_artifact(project_root: Path, item: dict[str, Any], artifact: str | None) -> bool:
    if not artifact:
        return True
    artifact_value = str(item.get("artifact") or "")
    if artifact_value and artifact_value != artifact:
        return False
    expected = item.get("artifact_sha256")
    if not expected:
        return True
    current = sha256_file(project_root / artifact)
    return bool(current and current == expected)


def project_start_approval_exists(
    project_root: Path,
    approvals: list[dict[str, Any]],
    approval_type: str,
    feature_id: str,
    artifact: str | None = None,
) -> bool:
    for item in approvals:
        if item.get("type") != approval_type:
            continue
        if item.get("flow") not in {"project_start", None, ""}:
            continue
        if item.get("feature_id") not in {feature_id, None, ""}:
            continue
        if not approval_event_matches_artifact(project_root, item, artifact):
            continue
        if item.get("approved_by") not in {"user", "human", None, ""}:
            continue
        return True
    return False


def approval_exists(approvals: list[dict[str, Any]], feature_id: str | None, checkpoints: set[str]) -> bool:
    for item in approvals:
        item_type = str(item.get("type") or "").lower().replace("-", "_")
        if item_type in {f"{checkpoint}_approved" for checkpoint in checkpoints}:
            if feature_id and item.get("feature_id") not in {feature_id, None, ""}:
                continue
            return True
        if item.get("decision") != "approved" or item.get("approver_type") != "human":
            continue
        if feature_id and item.get("feature_id") not in {feature_id, None, ""}:
            continue
        checkpoint = str(item.get("checkpoint") or "").lower().replace("-", "_")
        if checkpoint in checkpoints:
            return True
    return False


def latest_feature_dir(project_root: Path) -> Path | None:
    features_dir = project_root / "features"
    if not features_dir.exists():
        return None
    candidates = [p for p in features_dir.iterdir() if p.is_dir()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return candidates[0]


def evidence_green(path: Path) -> bool:
    data = read_json(path)
    status = str(data.get("status") or data.get("result") or "").lower()
    return data.get("passed") is True or data.get("success") is True or status in {"pass", "passed", "green", "ok", "success"}


def project_start_state_path(project_root: Path) -> Path:
    return project_root / ".engineer" / "project-start-state.json"


def project_start_artifact(project_root: Path, state_data: dict[str, Any], key: str, fallback: str) -> Path:
    artifacts = state_data.get("artifacts") if isinstance(state_data.get("artifacts"), dict) else {}
    value = artifacts.get(key) if isinstance(artifacts.get(key), str) else fallback
    return project_root / value


def infer_project_start_state(project_root: Path, ps_state: dict[str, Any], gates: dict[str, bool]) -> str:
    configured = str(ps_state.get("state") or "")
    if configured in PROJECT_START_STATES:
        if configured == "PLAN_APPROVED" and gates.get("approved_plan"):
            return "IMPLEMENTATION_ALLOWED"
        return configured
    if gates.get("approved_plan"):
        return "IMPLEMENTATION_ALLOWED"
    if gates.get("plan"):
        return "PLAN_DRAFTED"
    if gates.get("gherkin_spec"):
        return "SPEC_DRAFTED"
    if gates.get("acceptance_criteria"):
        return "ACS_DRAFTED"
    if gates.get("feature_charter"):
        return "CHARTER_DRAFTED"
    if project_start_state_path(project_root).exists() or (project_root / "features" / PROJECT_START_FEATURE_ID).exists():
        return "PROJECT_INTAKE"
    return "NO_DAE_STATE"


def inspect_state(project_root: Path) -> dict[str, Any]:
    state_path = project_root / ".engineer" / "dae-state.json"
    state_data = read_json(state_path)
    ps_state_path = project_start_state_path(project_root)
    ps_state = read_json(ps_state_path)
    project_start_active = bool(ps_state) or (project_root / "features" / PROJECT_START_FEATURE_ID).exists()
    active_feature = ps_state.get("feature_id") or state_data.get("active_feature") or state_data.get("feature_id")
    feature_dir = project_root / "features" / str(active_feature) if active_feature else latest_feature_dir(project_root)
    if feature_dir and feature_dir.exists():
        active_feature = feature_dir.name
    else:
        feature_dir = None
        active_feature = active_feature if isinstance(active_feature, str) else None
    approvals = read_approvals(project_root)
    paths: dict[str, Path | None] = {
        "charter": project_start_artifact(project_root, ps_state, "charter", "CHARTER.md") if project_start_active else None,
        "feature": feature_dir / "feature.md" if feature_dir else None,
        "acs": None,
        "spec": feature_dir / "spec.md" if feature_dir else None,
        "plan": feature_dir / "plan.md" if feature_dir else None,
        "progress": feature_dir / "progress.md" if feature_dir else None,
        "acceptance": feature_dir / "evidence" / "acceptance-tests.json" if feature_dir else None,
        "unit": feature_dir / "evidence" / "unit-tests.json" if feature_dir else None,
        "mutation": feature_dir / "evidence" / "mutation.json" if feature_dir else None,
        "crap": feature_dir / "evidence" / "crap.json" if feature_dir else None,
        "architecture": feature_dir / "evidence" / "architecture.json" if feature_dir else None,
        "refine": feature_dir / "evidence" / "refine.json" if feature_dir else None,
        "duplicate": feature_dir / "evidence" / "duplicate-detection.json" if feature_dir else None,
        "test_impact": feature_dir / "evidence" / "test-impact.json" if feature_dir else None,
    }
    if feature_dir:
        for name in ("acs.md", "acceptance-criteria.md", "acceptance_criteria.md"):
            candidate = feature_dir / name
            if candidate.exists():
                paths["acs"] = candidate
                break
    if not paths["spec"]:
        specs = sorted(project_root.glob("specs/*.txt")) + sorted(project_root.glob("specs/spec.md"))
        if specs:
            paths["spec"] = specs[0]
    if not paths["acs"] and paths["spec"] and paths["spec"].exists():
        paths["acs"] = paths["spec"]
    if project_start_active:
        feature_id = str(active_feature or PROJECT_START_FEATURE_ID)
        paths["charter"] = project_start_artifact(project_root, ps_state, "charter", "CHARTER.md")
        paths["feature"] = project_start_artifact(project_root, ps_state, "feature", f"features/{feature_id}/feature.md")
        paths["acs"] = paths["acs"] or project_start_artifact(project_root, ps_state, "acs", f"features/{feature_id}/acs.md")
        paths["spec"] = project_start_artifact(project_root, ps_state, "spec", f"features/{feature_id}/spec.md")
        paths["plan"] = project_start_artifact(project_root, ps_state, "plan", f"features/{feature_id}/plan.md")
        paths["progress"] = project_start_artifact(project_root, ps_state, "progress", f"features/{feature_id}/progress.md")

    def exists(key: str) -> bool:
        path = paths.get(key)
        return bool(path and path.exists())

    handoffs = list((feature_dir / "handoffs").glob("*")) if feature_dir and (feature_dir / "handoffs").exists() else []
    required = state_data.get("required_evidence") if isinstance(state_data.get("required_evidence"), dict) else {}
    missing_gates: list[str] = []
    plan_rel = project_rel(paths["plan"], project_root) if paths.get("plan") else None  # type: ignore[arg-type]
    feature_id = str(active_feature or PROJECT_START_FEATURE_ID)
    if project_start_active:
        gate_checks = {
            "feature_charter": exists("charter"),
            "acceptance_criteria": exists("acs") or exists("feature"),
            "gherkin_spec": exists("spec"),
            "plan": exists("plan"),
            "approved_plan": project_start_approval_exists(
                project_root,
                approvals,
                "plan_approved",
                feature_id,
                plan_rel,
            ),
        }
    else:
        gate_checks = {
            "feature_charter": exists("feature"),
            "acceptance_criteria": exists("acs"),
            "accepted_acceptance_criteria": approval_exists(approvals, active_feature, {"ac", "acs", "acceptance", "acceptance_criteria"}),
            "gherkin_spec": exists("spec"),
            "plan": exists("plan"),
            "approved_plan": approval_exists(approvals, active_feature, {"plan", "architecture"}),
        }
    for key, ok in gate_checks.items():
        if not ok:
            missing_gates.append(key)
    project_start_state = infer_project_start_state(project_root, ps_state, gate_checks)
    return {
        "project_root": str(project_root),
        "dae_enabled": True,
        "flow": "project_start" if project_start_active else "feature",
        "project_start_state": project_start_state,
        "active_feature": active_feature,
        "checkpoint": state_data.get("checkpoint") or infer_checkpoint(gate_checks),
        "feature_dir": str(feature_dir) if feature_dir else None,
        "artifacts": {k: str(v) for k, v in paths.items() if v},
        "approvals_path": str(project_root / ".engineer" / "approvals.jsonl"),
        "approvals": {
            "acceptance_criteria": gate_checks["accepted_acceptance_criteria"],
            "plan": gate_checks["approved_plan"],
        } if "accepted_acceptance_criteria" in gate_checks else {"plan": gate_checks["approved_plan"]},
        "gates": gate_checks,
        "missing_gates": missing_gates,
        "implementation_started": bool(state_data.get("implementation_started")),
        "touched_files": state_data.get("touched_files") if isinstance(state_data.get("touched_files"), list) else [],
        "evidence": {
            "acceptance_tests": exists("acceptance") and evidence_green(paths["acceptance"]),  # type: ignore[arg-type]
            "unit_tests": exists("unit") and evidence_green(paths["unit"]),  # type: ignore[arg-type]
            "progress": exists("progress"),
            "handoff": bool(handoffs),
            "mutation": exists("mutation") and evidence_green(paths["mutation"]),  # type: ignore[arg-type]
            "crap": exists("crap") and evidence_green(paths["crap"]),  # type: ignore[arg-type]
            "architecture": exists("architecture") and evidence_green(paths["architecture"]),  # type: ignore[arg-type]
            "refine": exists("refine") and evidence_green(paths["refine"]),  # type: ignore[arg-type]
            "duplicate_detection": exists("duplicate") and evidence_green(paths["duplicate"]),  # type: ignore[arg-type]
            "test_impact": exists("test_impact") and evidence_green(paths["test_impact"]),  # type: ignore[arg-type]
        },
        "required_evidence": required,
        "branch": current_branch(project_root),
    }


def infer_checkpoint(gates: dict[str, bool]) -> str:
    if not gates["feature_charter"]:
        return "feature-init"
    if not gates["acceptance_criteria"] or not gates.get("accepted_acceptance_criteria", True):
        return "acceptance-criteria"
    if not gates["gherkin_spec"]:
        return "spec"
    if not gates["plan"] or not gates["approved_plan"]:
        return "plan"
    return "implementation"


def current_branch(project_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return None
    branch = proc.stdout.strip()
    return branch or None


def missing_implementation_gates(state: dict[str, Any]) -> list[str]:
    return list(state.get("missing_gates") or [])


def is_generated_acceptance_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        ".build/generated/" in normalized
        or "tests/acceptance/generated/" in normalized
        or "generated-acceptance" in normalized
        or "acceptance-pipeline/generated" in normalized
    )


def is_spec_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.endswith("/spec.md") or normalized == "spec.md" or "/specs/" in f"/{normalized}"


def is_source_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if not normalized or normalized.endswith("/"):
        return False
    if is_generated_acceptance_path(normalized):
        return False
    if is_planning_artifact_path(normalized):
        return False
    suffix = Path(normalized).suffix.lower()
    if suffix in {".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt", ".rst"}:
        return False
    return suffix in SOURCE_EXTENSIONS or normalized.startswith(("src/", "lib/", "app/", "packages/"))


def is_implementation_affecting_path(path: str, project_root: Path | None = None) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    if not normalized or normalized.endswith("/"):
        return False
    if is_planning_artifact_path(normalized) or is_generated_acceptance_path(normalized):
        return False
    config: dict[str, Any] = {}
    if project_root is not None:
        config, _, _ = load_quality_config(project_root)
    detection = config.get("dirty_detection") if isinstance(config.get("dirty_detection"), dict) else {}
    globs = detection.get("implementation_affecting_globs")
    patterns = globs if isinstance(globs, list) and globs else list(BLOCKED_BEFORE_PLAN_APPROVED)
    if any(fnmatch.fnmatch(normalized, str(pattern)) for pattern in patterns):
        return True
    return is_source_path(normalized) or is_blocked_before_plan_path(normalized)


def is_planning_artifact_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in ALLOWED_BEFORE_PLAN_APPROVED)


def is_blocked_before_plan_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    if not normalized:
        return False
    if is_planning_artifact_path(normalized):
        return False
    comparable = normalized.rstrip("/")
    return any(
        fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(comparable, pattern.rstrip("/**"))
        for pattern in BLOCKED_BEFORE_PLAN_APPROVED
    )


def tool_input(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("tool_input") or event.get("input") or {}
    return value if isinstance(value, dict) else {}


def command_text(event: dict[str, Any]) -> str:
    input_data = tool_input(event)
    return str(input_data.get("command") or input_data.get("patch") or input_data.get("content") or "")


def candidate_write_paths(event: dict[str, Any]) -> list[str]:
    input_data = tool_input(event)
    paths: list[str] = []
    for key in ("file_path", "path", "target", "filename"):
        value = input_data.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    command = command_text(event)
    for pattern in WRITE_PATTERNS:
        for match in pattern.finditer(command):
            paths.append(match.group(1).strip().strip("'\""))
    if SCAFFOLD_COMMAND_RE.search(command):
        paths.append("package.json")
    mkdir_match = Mkdir_SOURCE_RE.search(command)
    if mkdir_match:
        for item in shlex.split(mkdir_match.group("paths")):
            if item.startswith("-"):
                continue
            paths.append(item.rstrip("/") + "/")
    return list(dict.fromkeys(paths))


def path_outside_workspace(path: str, root: Path) -> bool:
    candidate = Path(path)
    if not candidate.is_absolute():
        return False
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return True
    return False


def has_source_write(event: dict[str, Any], root: Path) -> bool:
    tool = str(event.get("tool_name") or "")
    if tool in {"apply_patch", "Edit", "Write"}:
        return any(is_source_path(project_rel((root / p) if not Path(p).is_absolute() else Path(p), root)) for p in candidate_write_paths(event))
    command = command_text(event)
    if not command:
        return False
    return any(is_source_path(project_rel((root / p) if not Path(p).is_absolute() else Path(p), root)) for p in candidate_write_paths(event))


def blocked_write_paths_before_plan(event: dict[str, Any], root: Path) -> list[str]:
    blocked: list[str] = []
    for path in candidate_write_paths(event):
        rel = project_rel((root / path) if not Path(path).is_absolute() else Path(path), root)
        if is_blocked_before_plan_path(rel) or is_source_path(rel):
            blocked.append(rel)
    return list(dict.fromkeys(blocked))


def has_dangerous_command(text: str) -> bool:
    return bool(DESTRUCTIVE_RE.search(text) or UNSAFE_PERMISSION_RE.search(text))


def command_has_write_intent(event: dict[str, Any]) -> bool:
    if str(event.get("tool_name") or "") in {"apply_patch", "Edit", "Write"}:
        return True
    return bool(candidate_write_paths(event))


def spec_leakage_in_text(text: str) -> bool:
    return bool(SPEC_LEAKAGE_RE.search(text))


def persist_implementation_touch(project_root: Path, paths: list[str]) -> None:
    engineer_dir = project_root / ".engineer"
    engineer_dir.mkdir(parents=True, exist_ok=True)
    state_path = engineer_dir / "dae-state.json"
    state = read_json(state_path)
    touched = state.get("touched_files") if isinstance(state.get("touched_files"), list) else []
    for path in paths:
        if path not in touched:
            touched.append(path)
    state["schema_version"] = state.get("schema_version") or "1.0"
    state["updated_at"] = now_iso()
    state["implementation_started"] = True
    state["touched_files"] = touched
    quality_state = mark_quality_dirty(project_root, paths, "implementation_affecting_edit")
    state["required_evidence"] = {gate: True for gate in quality_state.get("required_evidence", [])}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_project_start_state(project_root: Path, prompt_intent: str) -> Path:
    state_path = project_start_state_path(project_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = read_json(state_path)
    if not state:
        state = {
            "version": 1,
            "flow": "project_start",
            "state": "PROJECT_INTAKE",
            "feature_id": PROJECT_START_FEATURE_ID,
            "artifacts": {
                "charter": "CHARTER.md",
                "feature": f"features/{PROJECT_START_FEATURE_ID}/feature.md",
                "acs": f"features/{PROJECT_START_FEATURE_ID}/acs.md",
                "spec": f"features/{PROJECT_START_FEATURE_ID}/spec.md",
                "plan": f"features/{PROJECT_START_FEATURE_ID}/plan.md",
                "progress": f"features/{PROJECT_START_FEATURE_ID}/progress.md",
            },
            "approvals": {
                "charter_approved": False,
                "spec_approved": False,
                "plan_approved": False,
            },
        }
    state["last_prompt_intent"] = prompt_intent
    state["updated_at"] = now_iso()
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state_path


def record_project_start_plan_approval(project_root: Path, prompt: str) -> tuple[bool, str]:
    ensure_project_start_state(project_root, "approval_intent")
    state = inspect_state(project_root)
    feature_id = str(state.get("active_feature") or PROJECT_START_FEATURE_ID)
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), dict) else {}
    plan_path = Path(str(artifacts.get("plan") or project_root / "features" / feature_id / "plan.md"))
    if not plan_path.exists():
        return False, "Plan approval was not recorded because the project-start plan artifact does not exist."
    rel = project_rel(plan_path, project_root)
    digest = sha256_file(plan_path)
    if not digest:
        return False, "Plan approval was not recorded because the plan hash could not be computed."
    approvals = project_root / ".engineer" / "approvals.jsonl"
    approvals.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "type": "plan_approved",
        "flow": "project_start",
        "feature_id": feature_id,
        "artifact": rel,
        "artifact_sha256": digest,
        "approved_by": "user",
        "approved_at": now_iso(),
        "source": "user_prompt_submit",
        "prompt_excerpt": prompt[:240],
    }
    with approvals.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    state_path = project_start_state_path(project_root)
    state_data = read_json(state_path)
    approvals_state = state_data.get("approvals") if isinstance(state_data.get("approvals"), dict) else {}
    approvals_state["plan_approved"] = True
    state_data["approvals"] = approvals_state
    state_data["state"] = "PLAN_APPROVED"
    state_data["updated_at"] = now_iso()
    state_path.write_text(json.dumps(state_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True, f"Recorded non-stale project-start plan approval for {rel}."


def cmd_session_start(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    state = inspect_state(root)
    quality = effective_quality_status(root)
    missing = state.get("missing_gates") or []
    pending_quality = quality.get("blocking_gates") or quality.get("required_gates") or []
    message = (
        "DAE runtime context loaded. Pipeline: onboard/reorient -> feature-init -> ACs -> "
        "Gherkin spec -> approved plan -> implementation -> refine -> verify. "
        f"Project-start state: {state.get('project_start_state')}; checkpoint: {state.get('checkpoint')}; "
        f"active feature: {state.get('active_feature') or 'none'}; "
        f"missing gates: {', '.join(missing) if missing else 'none'}. "
        f"Quality gates: profile={quality.get('profile')}, dirty={quality.get('quality_dirty')}, "
        f"pending={', '.join(pending_quality) if pending_quality else 'none'}. "
        f"Next legal quality action: {'quality-verify' if pending_quality else 'continue DAE pipeline'}. "
        "Hard gates cover supported prompt/tool/permission/stop events; non-managed hooks still require Codex trust."
    )
    write_audit(event, root, "dae.session_context_loaded", "context", message)
    emit_context(message)
    return 0


def cmd_user_prompt_submit(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    prompt = str(event.get("prompt") or event.get("user_prompt") or event.get("message") or "")
    bypass = bool(BYPASS_PROMPT_RE.search(prompt))
    disable = bool(re.search(r"(disable|turn\s+off|remove)\s+(dae|hooks|guardrails)|отключи\s+(dae|хуки|guard)", prompt, re.IGNORECASE))
    if bypass or disable:
        state = inspect_state(root)
        missing = missing_implementation_gates(state)
        message = (
            "dae.pipeline_order: DAE blocks prompts that explicitly bypass project-start intake, acceptance criteria, "
            "Gherkin specs, plan approval, hooks, or guardrails. Start with project intake."
        )
        write_audit(event, root, "dae.pipeline_order", "block", message, missing)
        emit_block(message)
        return 0
    quality = effective_quality_status(root)
    if FINALIZE_PROMPT_RE.search(prompt) and quality.get("quality_dirty") and quality.get("blocking_gates"):
        message = (
            "dae.quality_gates_required: feature quality is dirty; completion/release requires quality-verify first. "
            f"Pending gates: {', '.join(quality.get('blocking_gates') or [])}."
        )
        write_audit(event, root, "dae.two_test_streams_required", "block", message, list(quality.get("blocking_gates") or []))
        emit_block(message)
        return 0
    if PLANNING_ONLY_PROMPT_RE.search(prompt):
        ensure_project_start_state(root, "planning_only")
        message = (
            "Planning-only request. You may discuss and draft DAE planning artifacts, but "
            "implementation/scaffold writes remain blocked until explicit plan approval."
        )
        write_audit(event, root, "dae.pipeline_order", "context", message)
        emit_context(message)
        return 0
    if APPROVAL_PROMPT_RE.search(prompt):
        ok, message = record_project_start_plan_approval(root, prompt)
        write_audit(event, root, "dae.plan_human_approved", "allow" if ok else "block", message)
        if ok:
            emit_context(message + " Implementation may proceed only while the approved plan hash remains current.")
        else:
            emit_block(message)
        return 0
    if NEW_PROJECT_PROMPT_RE.search(prompt):
        ensure_project_start_state(root, "new_project_creation")
        state = inspect_state(root)
        message = (
            "DAE project-start intake required. Do not edit scaffold/source/config/test files. "
            "Draft a project charter, make explicit assumptions, ask only the minimum necessary "
            "clarifying questions, and request approval before ACs/specs/plan. "
            f"Current state: {state.get('project_start_state')}. Implementation remains blocked until "
            "charter, ACs, Gherkin spec, plan, and non-stale human plan approval exist."
        )
        write_audit(event, root, "dae.pipeline_order", "context", message, missing_implementation_gates(state))
        emit_context(message)
        return 0
    state = inspect_state(root)
    missing = missing_implementation_gates(state)
    implementation = bool(IMPLEMENTATION_PROMPT_RE.search(prompt))
    workflow = bool(WORKFLOW_PROMPT_RE.search(prompt))
    if implementation and not workflow and missing:
        rule = "dae.source_write_requires_gates"
        message = (
            f"{rule}: implementation is blocked until DAE gates exist: {', '.join(missing)}. "
            f"Next legal action: run {state.get('checkpoint')} workflow and record human approvals."
        )
        write_audit(event, root, rule, "block", message, missing)
        emit_block(message)
        return 0
    if workflow:
        message = (
            f"DAE workflow prompt allowed. Current checkpoint: {state.get('checkpoint')}; "
            f"missing gates: {', '.join(missing) if missing else 'none'}."
        )
        if quality.get("quality_dirty") and quality.get("blocking_gates"):
            message += (
                " Quality gates are pending before completion/release: "
                f"{', '.join(quality.get('blocking_gates') or [])}. Run quality-verify when ready."
            )
        write_audit(event, root, "dae.pipeline_order", "context", message, missing)
        emit_allow_context(message)
        return 0
    if quality.get("quality_dirty") and quality.get("blocking_gates"):
        message = (
            "dae.quality_gates_required: quality gates are pending before completion/release: "
            f"{', '.join(quality.get('blocking_gates') or [])}. Run quality-verify when ready."
        )
        write_audit(event, root, "dae.two_test_streams_required", "context", message, list(quality.get("blocking_gates") or []))
        emit_context(message)
        return 0
    write_audit(event, root, "dae.audit_log_required", "allow", "Prompt allowed without DAE intervention.")
    return 0


def cmd_pre_tool_use(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    state = inspect_state(root)
    command = command_text(event)
    paths = candidate_write_paths(event)
    tool = str(event.get("tool_name") or "")
    unsafe_paths = [p for p in paths if path_outside_workspace(p, root)]
    quality = effective_quality_status(root)
    if (RELEASE_COMMAND_RE.search(command) or QUALITY_BYPASS_RE.search(command)) and quality.get("quality_dirty"):
        missing = list(quality.get("blocking_gates") or quality.get("required_gates") or [])
        message = (
            "dae.quality_gates_required: release/finalization action denied while quality is dirty or failing. "
            f"Run quality-verify and provide passing evidence for: {', '.join(missing) if missing else 'quality gates'}."
        )
        write_audit(event, root, "dae.two_test_streams_required", "deny", message, missing, tool)
        emit_deny(message)
        return 0
    if has_dangerous_command(command):
        message = "dae.destructive_command_denied: destructive or permission-bypass command denied by DAE."
        write_audit(event, root, "dae.destructive_command_denied", "deny", message, tool_name=tool)
        emit_deny(message)
        return 0
    if unsafe_paths:
        message = "dae.out_of_workspace_write_denied: write outside workspace denied: " + ", ".join(unsafe_paths)
        write_audit(event, root, "dae.out_of_workspace_write_denied", "deny", message, unsafe_paths, tool)
        emit_deny(message)
        return 0
    generated = [p for p in paths if is_generated_acceptance_path(p)]
    if generated:
        message = "dae.generated_acceptance_tests_immutable: generated acceptance tests must be regenerated, not edited."
        write_audit(event, root, "dae.generated_acceptance_tests_immutable", "deny", message, generated, tool)
        emit_deny(message)
        return 0
    spec_paths = [p for p in paths if is_spec_path(p)]
    if spec_paths and spec_leakage_in_text(command):
        message = "dae.spec_leakage_forbidden: spec edits must describe external observables only."
        write_audit(event, root, "dae.spec_leakage_forbidden", "deny", message, spec_paths, tool)
        emit_deny(message)
        return 0
    blocked_paths = blocked_write_paths_before_plan(event, root)
    if command_has_write_intent(event) and blocked_paths:
        missing = missing_implementation_gates(state)
        if missing:
            message = (
                "dae.source_write_requires_gates: source write denied until AC/spec/plan/human approval "
                f"gates are complete. Missing: {', '.join(missing)}."
            )
            write_audit(event, root, "dae.source_write_requires_gates", "deny", message, missing + blocked_paths, tool)
            emit_deny(message)
            return 0
    write_audit(event, root, "dae.audit_log_required", "allow", "PreToolUse allowed.", tool_name=tool)
    return 0


def cmd_post_tool_use(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    paths = candidate_write_paths(event)
    tool = str(event.get("tool_name") or "")
    source_paths = [
        p
        for p in paths
        if is_implementation_affecting_path(project_rel((root / p) if not Path(p).is_absolute() else Path(p), root), root)
    ]
    generated = [p for p in paths if is_generated_acceptance_path(p)]
    spec_paths = [p for p in paths if is_spec_path(p)]
    messages: list[str] = []
    if source_paths:
        persist_implementation_touch(root, source_paths)
        quality = effective_quality_status(root)
        pending = quality.get("required_gates") or []
        messages.append(
            "Implementation-affecting edit audited; quality_dirty=true. "
            "Stop and release actions require quality evidence. "
            f"Required gates: {', '.join(pending)}. Run quality-verify; heavy analyzers were not run on this edit."
        )
        write_audit(event, root, "dae.two_test_streams_required", "warn", messages[-1], source_paths, tool)
    if generated:
        messages.append("Generated acceptance tests were touched after tool execution; regenerate them from specs.")
        write_audit(event, root, "dae.generated_acceptance_tests_immutable", "warn", messages[-1], generated, tool)
    if spec_paths and spec_leakage_in_text(command_text(event)):
        messages.append("Spec leakage detected after edit; remove implementation details from specs.")
        write_audit(event, root, "dae.spec_leakage_forbidden", "warn", messages[-1], spec_paths, tool)
    if messages:
        emit_context(" ".join(messages))
    else:
        write_audit(event, root, "dae.audit_log_required", "audit", "PostToolUse audited.", tool_name=tool)
    return 0


def cmd_permission_request(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    text = " ".join(
        [
            str(event.get("permission_mode") or ""),
            str(event.get("reason") or event.get("description") or ""),
            command_text(event),
        ]
    )
    paths = candidate_write_paths(event)
    unsafe_paths = [p for p in paths if path_outside_workspace(p, root)]
    if has_dangerous_command(text) or unsafe_paths or QUALITY_BYPASS_RE.search(text):
        missing = unsafe_paths if unsafe_paths else []
        message = "dae.unsafe_permission_denied: unsafe escalation, destructive action, or out-of-workspace write denied."
        write_audit(event, root, "dae.unsafe_permission_denied", "deny", message, missing, str(event.get("tool_name") or ""))
        emit_deny(message)
        return 0
    write_audit(event, root, "dae.audit_log_required", "allow", "Permission request left to normal Codex flow.")
    return 0


def missing_finish_evidence(state: dict[str, Any]) -> list[str]:
    evidence = state.get("evidence") or {}
    missing = []
    for key in ("acceptance_tests", "unit_tests", "progress", "handoff"):
        if not evidence.get(key):
            missing.append(key)
    required = state.get("required_evidence") or {}
    configured = {
        "mutation": "mutation_workflow",
        "crap": "crap_analysis",
        "architecture": "architecture_check",
        "refine": "refine_review",
        "duplicate_detection": "duplicate_detection",
        "test_impact": "test_impact",
    }
    for key, label in configured.items():
        if required.get(key) and not evidence.get(key):
            missing.append(label)
    return missing


def quality_blockers(project_root: Path) -> list[str]:
    quality = effective_quality_status(project_root)
    if not quality.get("quality_dirty"):
        return []
    return list(quality.get("blocking_gates") or [])


def cmd_stop(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    if event.get("stop_hook_active") is True:
        write_audit(event, root, "dae.audit_log_required", "allow", "Stop hook recursion guard allowed completion.")
        return 0
    state = inspect_state(root)
    last_message = str(event.get("last_assistant_message") or "")
    feature_done_claim = bool(re.search(r"\b(done|complete|implemented|готово|сделано|реализ)\b", last_message, re.IGNORECASE))
    if state.get("implementation_started") or feature_done_claim:
        quality_state = load_quality_state(root)
        if feature_done_claim and not state.get("implementation_started") and not quality_state.get("quality_dirty"):
            mark_quality_dirty(root, ["<completion-claim>"], "completion_claim_without_quality_evidence", event)
        missing = quality_blockers(root)
        if missing:
            message = (
                "dae.quality_gates_required: cannot finish feature work yet. "
                f"Missing or failing quality evidence: {', '.join(missing)}. Next legal action: run quality-verify, "
                "produce machine-readable evidence under features/<feature>/evidence/quality/, update progress, and add a handoff summary."
            )
            write_audit(event, root, "dae.two_test_streams_required", "continue", message, missing)
            emit_continue(message)
            return 0
    write_audit(event, root, "dae.audit_log_required", "allow", "Stop allowed.")
    return 0


def validate_contract() -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        data = load_contract()
    except Exception as exc:
        return False, [f"contract JSON failed to load: {exc}"]
    if data.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    rules = data.get("rules")
    if not isinstance(rules, list):
        errors.append("rules must be a list")
        rules = []
    seen: set[str] = set()
    required_fields = {"id", "title", "description", "severity", "events", "enforcement_mode", "detector", "hard_gate_supported", "audit_required", "message", "docs"}
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(f"rule {index} must be an object")
            continue
        missing = sorted(required_fields - set(rule))
        if missing:
            errors.append(f"{rule.get('id', index)} missing fields: {missing}")
        rule_id = str(rule.get("id") or "")
        seen.add(rule_id)
        for event_name in rule.get("events") or []:
            if event_name not in KNOWN_EVENTS:
                errors.append(f"{rule_id} has unknown event {event_name}")
        modes = rule.get("enforcement_mode") or {}
        if not isinstance(modes, dict):
            errors.append(f"{rule_id} enforcement_mode must be object")
            continue
        for event_name, mode in modes.items():
            if event_name != "docs" and event_name not in KNOWN_EVENTS:
                errors.append(f"{rule_id} has mode for unknown event {event_name}")
            if mode not in VALID_MODES:
                errors.append(f"{rule_id} has invalid mode {mode}")
        if not str(rule.get("detector") or "").strip():
            errors.append(f"{rule_id} detector is empty")
        if rule.get("severity") == "critical" and "hard_gate" not in set(modes.values()) and "platform_limit" not in set(modes.values()):
            errors.append(f"{rule_id} critical rule lacks hard_gate or platform_limit")
    missing_rules = sorted(REQUIRED_RULE_IDS - seen)
    if missing_rules:
        errors.append(f"missing required rules: {missing_rules}")
    return not errors, errors


def cmd_validate_contract(_: dict[str, Any]) -> int:
    ok, errors = validate_contract()
    result = {"status": "PASS" if ok else "FAIL", "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def wrapper_scripts(root: Path) -> list[Path]:
    return [
        root / "hooks" / "scripts" / "dae-session-start.sh",
        root / "hooks" / "scripts" / "dae-user-prompt-submit.sh",
        root / "hooks" / "scripts" / "dae-pre-tool-use.sh",
        root / "hooks" / "scripts" / "dae-post-tool-use.sh",
        root / "hooks" / "scripts" / "dae-permission-request.sh",
        root / "hooks" / "scripts" / "dae-stop.sh",
    ]


def cmd_doctor(event: dict[str, Any]) -> int:
    root = script_root()
    project_root = discover_project_root(event)
    checks: list[dict[str, Any]] = []
    ok, errors = validate_contract()
    checks.append({"name": "contract", "status": "PASS" if ok else "FAIL", "details": errors})
    project_contract = root / "guardrails" / "dae-project-start-contract.json"
    try:
        project_contract_data = json.loads(project_contract.read_text(encoding="utf-8"))
        missing_project_keys = [
            key
            for key in ("states", "rules", "allowed_before_plan_approved", "blocked_before_plan_approved")
            if key not in project_contract_data
        ]
        checks.append(
            {
                "name": "project_start_contract",
                "status": "PASS" if not missing_project_keys else "FAIL",
                "details": missing_project_keys or [str(project_contract)],
            }
        )
    except Exception as exc:
        checks.append({"name": "project_start_contract", "status": "FAIL", "details": [str(exc)]})
    hooks_path = root / "hooks" / "hooks.json"
    try:
        hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
        missing = sorted(KNOWN_EVENTS - set((hooks.get("hooks") or {}).keys()))
        checks.append({"name": "hooks_json", "status": "PASS" if not missing else "FAIL", "details": missing})
    except Exception as exc:
        checks.append({"name": "hooks_json", "status": "FAIL", "details": [str(exc)]})
    manifest = root / ".codex-plugin" / "plugin.json"
    manifest_data = read_json(manifest)
    checks.append({"name": "manifest_hooks", "status": "PASS" if manifest_data.get("hooks") else "FAIL", "details": [manifest_data.get("hooks")]})
    evidence_schema = root / "guardrails" / "quality-evidence.schema.json"
    checks.append({"name": "quality_evidence_schema", "status": "PASS" if evidence_schema.exists() else "FAIL", "details": [str(evidence_schema)]})
    quality_config, quality_loaded, quality_errors = load_quality_config(project_root)
    quality_gates = quality_config.get("gates") if isinstance(quality_config.get("gates"), dict) else {}
    checks.append(
        {
            "name": "quality_config",
            "status": "PASS" if not quality_errors else "FAIL",
            "details": quality_errors or quality_loaded,
        }
    )
    checks.append(
        {
            "name": "quality_crap_required",
            "status": "PASS" if isinstance(quality_gates.get("crap"), dict) and quality_gates["crap"].get("mode") == "required" else "FAIL",
            "details": [str(quality_gates.get("crap"))],
        }
    )
    for wrapper in wrapper_scripts(root):
        checks.append({"name": f"wrapper:{wrapper.name}", "status": "PASS" if os.access(wrapper, os.X_OK) else "FAIL", "details": [str(wrapper)]})
    try:
        audit_dir = plugin_data_root(project_root)
        audit_dir.mkdir(parents=True, exist_ok=True)
        test_path = audit_dir / ".doctor-write-test"
        test_path.write_text("ok\n", encoding="utf-8")
        test_path.unlink()
        checks.append({"name": "audit_writable", "status": "PASS", "details": [str(audit_dir)]})
    except Exception as exc:
        checks.append({"name": "audit_writable", "status": "FAIL", "details": [str(exc)]})
    status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    print(json.dumps({"status": status, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


def cmd_state(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    print(json.dumps(inspect_state(root), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_quality_config(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    config, loaded, errors = load_quality_config(root)
    status = effective_quality_status(root)
    output = {
        "status": "PASS" if not errors else "FAIL",
        "loaded": loaded,
        "errors": errors,
        "audit": {
            "config_files_loaded": loaded,
            "profile": config.get("profile", "strict"),
            "relaxed_gates": status.get("relaxed_gates", []),
            "thresholds": ((config.get("gates") or {}).get("crap") or {}).get("thresholds", {}) if isinstance(config.get("gates"), dict) else {},
            "invalid_or_missing_fields": errors,
            "active_feature": status.get("active_feature"),
            "required_evidence": status.get("required_gates", []),
        },
        "effective_config": config,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


def cmd_validate_quality_config(event: dict[str, Any]) -> int:
    return cmd_quality_config(event)


def cmd_quality_status(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    status = effective_quality_status(root)
    print(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status.get("status") == "PASS" else 1


def cmd_quality_mark_dirty(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    paths = candidate_write_paths(event)
    explicit = event.get("changed_files")
    if isinstance(explicit, list):
        paths.extend(str(item) for item in explicit)
    if not paths:
        paths = ["<manual-quality-dirty>"]
    state = mark_quality_dirty(root, paths, str(event.get("reason") or "manual_quality_mark_dirty"), event)
    print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_quality_required_evidence(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    status = effective_quality_status(root)
    print(json.dumps({"required_evidence": status.get("required_gates", []), "quality_dirty": status.get("quality_dirty")}, ensure_ascii=False, indent=2))
    return 0


def cmd_quality_validate_evidence(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    status = effective_quality_status(root)
    print(json.dumps({"status": status.get("status"), "gate_results": status.get("gate_results"), "blocking_gates": status.get("blocking_gates")}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status.get("status") == "PASS" else 1


def cmd_quality_record_evidence(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    gate = str(event.get("gate") or "")
    source = event.get("path") or event.get("evidence")
    if gate not in QUALITY_GATE_NAMES or not isinstance(source, str):
        print(json.dumps({"status": "FAIL", "errors": ["quality-record-evidence requires gate and path"]}, indent=2))
        return 2
    inspected = inspect_state(root)
    feature_dir = active_feature_path(root, inspected)
    config, _, errors = load_quality_config(root)
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        return 1
    src_path = Path(source)
    if not src_path.is_absolute():
        src_path = root / src_path
    data = read_json(src_path)
    validation_errors = validate_quality_evidence_data(gate, data, config, parse_iso(load_quality_state(root).get("dirty_since")))
    if validation_errors:
        print(json.dumps({"status": "FAIL", "errors": validation_errors}, indent=2))
        return 1
    dest = quality_evidence_candidates(root, feature_dir, gate, config)[0]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    append_quality_audit(root, "quality_record_evidence", {"gate": gate, "evidence": project_rel(dest, root)})
    print(json.dumps({"status": "PASS", "gate": gate, "evidence": project_rel(dest, root)}, indent=2))
    return 0


def write_quality_summary(project_root: Path, status: dict[str, Any]) -> Path:
    feature_dir = active_feature_path(project_root)
    summary_path = quality_evidence_dir(project_root, feature_dir) / "quality-gate-summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": 1,
        "status": status.get("status"),
        "profile": status.get("profile"),
        "active_feature": status.get("active_feature"),
        "quality_dirty": bool(status.get("quality_dirty")) and status.get("status") != "PASS",
        "required_gates": status.get("required_gates", []),
        "gate_results": status.get("gate_results", {}),
        "relaxed_gates": status.get("relaxed_gates", []),
        "config_files": status.get("config_files", []),
        "config_errors": status.get("config_errors", []),
        "generated_at": now_iso(),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary_path


def cmd_quality_verify(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    status = effective_quality_status(root)
    summary_path = write_quality_summary(root, status)
    state = load_quality_state(root)
    state["last_summary"] = project_rel(summary_path, root)
    if status.get("status") == "PASS":
        state["quality_dirty"] = False
        state["cleared_at"] = now_iso()
    write_quality_state(root, state)
    append_quality_audit(root, "quality_verify", {"status": status.get("status"), "summary": project_rel(summary_path, root), "blocking_gates": status.get("blocking_gates", [])})
    output = {**status, "summary_path": project_rel(summary_path, root)}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status.get("status") == "PASS" else 1


def cmd_quality_reset_dirty(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    status = effective_quality_status(root)
    if status.get("status") != "PASS":
        print(json.dumps({"status": "FAIL", "errors": ["quality-reset-dirty requires passing quality status"], "blocking_gates": status.get("blocking_gates", [])}, indent=2))
        return 1
    state = load_quality_state(root)
    state["quality_dirty"] = False
    state["cleared_at"] = now_iso()
    write_quality_state(root, state)
    append_quality_audit(root, "quality_reset_dirty", {"status": "PASS"})
    print(json.dumps({"status": "PASS", "quality_dirty": False}, indent=2))
    return 0


def cmd_quality_doctor(event: dict[str, Any]) -> int:
    root = discover_project_root(event)
    config, loaded, errors = load_quality_config(root)
    status = effective_quality_status(root)
    checks = [
        {"name": "quality_default_config_exists", "status": "PASS" if quality_default_config_path().exists() else "FAIL", "details": [str(quality_default_config_path())]},
        {"name": "quality_config_valid", "status": "PASS" if not errors else "FAIL", "details": errors or loaded},
        {"name": "quality_crap_required", "status": "PASS" if ((config.get("gates") or {}).get("crap") or {}).get("mode") == "required" else "FAIL", "details": [str(((config.get("gates") or {}).get("crap") or {}).get("mode"))]},
        {"name": "quality_state_writable", "status": "PASS", "details": [str(quality_state_path(root))]},
        {"name": "quality_status", "status": status.get("status"), "details": status.get("blocking_gates", [])},
    ]
    try:
        quality_state_path(root).parent.mkdir(parents=True, exist_ok=True)
        probe = quality_state_path(root).parent / ".quality-doctor-write-test"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
    except Exception as exc:
        checks[3] = {"name": "quality_state_writable", "status": "FAIL", "details": [str(exc)]}
    overall = "PASS" if all(c["status"] == "PASS" for c in checks[:4]) else "FAIL"
    print(json.dumps({"status": overall, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if overall == "PASS" else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subcommand", choices=sorted(REQUIRED_SUBCOMMANDS))
    args = parser.parse_args(argv)
    event = load_stdin_json()
    dispatch = {
        "session-start": cmd_session_start,
        "user-prompt-submit": cmd_user_prompt_submit,
        "pre-tool-use": cmd_pre_tool_use,
        "post-tool-use": cmd_post_tool_use,
        "permission-request": cmd_permission_request,
        "stop": cmd_stop,
        "doctor": cmd_doctor,
        "state": cmd_state,
        "validate-contract": cmd_validate_contract,
        "quality-config": cmd_quality_config,
        "validate-quality-config": cmd_validate_quality_config,
        "quality-status": cmd_quality_status,
        "quality-mark-dirty": cmd_quality_mark_dirty,
        "quality-required-evidence": cmd_quality_required_evidence,
        "quality-validate-evidence": cmd_quality_validate_evidence,
        "quality-record-evidence": cmd_quality_record_evidence,
        "quality-verify": cmd_quality_verify,
        "quality-reset-dirty": cmd_quality_reset_dirty,
        "quality-doctor": cmd_quality_doctor,
    }
    return dispatch[args.subcommand](event)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
