#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
GUARD = REPO / "plugins" / "engineer" / "scripts" / "dae_guard.py"


def run_guard(subcommand: str, event: dict[str, Any], root: Path) -> tuple[int, dict[str, Any] | None, str]:
    env = os.environ.copy()
    env["CODEX_PROJECT_DIR"] = str(root)
    env["PLUGIN_ROOT"] = str(REPO / "plugins" / "engineer")
    env["PLUGIN_DATA"] = str(root / ".plugin-data")
    proc = subprocess.run(
        ["python3", str(GUARD), subcommand],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        cwd=str(root),
        env=env,
        check=False,
        timeout=30,
    )
    parsed = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, parsed, proc.stderr


def init_feature(root: Path) -> None:
    (root / ".git").mkdir()
    feature = root / "features" / "001-demo"
    feature.mkdir(parents=True)
    (root / ".engineer").mkdir()
    (root / ".engineer" / "dae-state.json").write_text(
        '{"schema_version":"1.0","active_feature":"001-demo","implementation_started":true}\n',
        encoding="utf-8",
    )


def init_approved_feature(root: Path) -> None:
    init_feature(root)
    feature = root / "features" / "001-demo"
    for name in ("feature.md", "acs.md", "spec.md", "plan.md"):
        (feature / name).write_text(f"# {name}\n", encoding="utf-8")
    approvals = root / ".engineer" / "approvals.jsonl"
    for checkpoint in ("acceptance_criteria", "plan"):
        with approvals.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "timestamp": "2026-05-22T00:00:00Z",
                        "feature_id": "001-demo",
                        "checkpoint": checkpoint,
                        "artifact": f"features/001-demo/{checkpoint}.md",
                        "decision": "approved",
                        "approver_type": "human",
                    }
                )
                + "\n"
            )


def evidence(root: Path, gate: str, status: str = "PASS", **extra: Any) -> None:
    out = root / "features" / "001-demo" / "evidence" / "quality"
    out.mkdir(parents=True, exist_ok=True)
    filenames = {
        "branch_hygiene": "branch-hygiene.json",
        "duplicate_detection": "duplicate-detection.json",
        "test_impact": "test-impact.json",
        "generated_acceptance_immutability": "generated-acceptance-immutability.json",
    }
    data: dict[str, Any] = {
        "schema_version": 1,
        "gate": gate,
        "status": status,
        "generated_at": "2099-01-01T00:00:00Z",
        "feature": "features/001-demo",
        "changed_files": ["src/app.py"],
        "command": f"probe {gate}",
        "artifacts": [],
        "summary": {},
        "limitations": [],
    }
    data.update(extra)
    (out / filenames.get(gate, f"{gate}.json")).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def all_evidence(root: Path) -> None:
    for gate in (
        "acceptance",
        "unit",
        "arch",
        "refine",
        "branch_hygiene",
        "progress",
        "handoff",
        "duplicate_detection",
        "test_impact",
        "generated_acceptance_immutability",
    ):
        evidence(root, gate)
    evidence(
        root,
        "crap",
        tool="crap-analyzer",
        coverage_source="coverage.xml",
        thresholds={
            "max_crap_score": 30,
            "warn_crap_score": 20,
            "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded",
            "max_high_risk_findings": 0,
        },
        summary={"changed_functions": 1, "max_crap_score": 8.0, "high_risk_findings": 0},
        findings=[],
    )


def result(item_id: str, ok: bool, evidence_paths: list[str], commands: list[str], notes: str = "") -> dict[str, Any]:
    return {"id": item_id, "status": "PASS" if ok else "FAIL", "evidence": evidence_paths, "commands": commands, "notes": notes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".dae-quality-gate-enforcement")
    args = parser.parse_args()
    out = Path(args.out)
    reports = out / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_approved_feature(root)
        post = {
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"},
        }
        code, parsed, _ = run_guard("post-tool-use", post, root)
        state = json.loads((root / ".engineer" / "quality-state.json").read_text(encoding="utf-8"))
        results.append(result("source_edit_after_plan_approval_marks_quality_dirty", code == 0 and state["quality_dirty"], [str(root / ".engineer" / "quality-state.json")], ["dae_guard.py post-tool-use"]))
        results.append(result("crap_required_by_default", "crap" in state["required_evidence"], [str(root / ".engineer" / "quality-state.json")], ["dae_guard.py post-tool-use"]))
        results.append(result("acceptance_unit_required_by_default", {"acceptance", "unit"}.issubset(set(state["required_evidence"])), [str(root / ".engineer" / "quality-state.json")], ["dae_guard.py post-tool-use"]))
        results.append(result("engineer_quality_checks_required_by_default", {"arch", "refine", "branch_hygiene", "progress", "handoff", "duplicate_detection", "test_impact"}.issubset(set(state["required_evidence"])), [str(root / ".engineer" / "quality-state.json")], ["dae_guard.py post-tool-use"]))
        code, parsed, _ = run_guard("session-start", {"hook_event_name": "SessionStart"}, root)
        results.append(result("session_start_surfaces_pending_quality", parsed is not None and "pending=" in parsed["hookSpecificOutput"].get("additionalContext", "") and "crap" in parsed["hookSpecificOutput"].get("additionalContext", ""), [], ["dae_guard.py session-start"]))
        code, parsed, _ = run_guard("user-prompt-submit", {"hook_event_name": "UserPromptSubmit", "prompt": "Continue with quality-verify workflow."}, root)
        results.append(result("user_prompt_surfaces_pending_quality", parsed is not None and "quality gates are pending" in parsed["hookSpecificOutput"].get("additionalContext", "").lower(), [], ["dae_guard.py user-prompt-submit"]))
        code, parsed, _ = run_guard("stop", {"hook_event_name": "Stop", "last_assistant_message": "Done."}, root)
        results.append(result("stop_blocks_missing_crap", parsed is not None and parsed.get("decision") == "block" and "crap" in parsed.get("reason", ""), [], ["dae_guard.py stop"]))
        code, parsed, _ = run_guard("pre-tool-use", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git commit -m demo"}}, root)
        results.append(result("git_commit_blocked_while_dirty", parsed is not None and parsed["hookSpecificOutput"].get("permissionDecision") == "deny", [], ["dae_guard.py pre-tool-use"]))
        code, parsed, _ = run_guard("permission-request", {"hook_event_name": "PermissionRequest", "tool_name": "Bash", "reason": "skip quality gates and force release", "tool_input": {"command": "git push"}}, root)
        results.append(result("permission_request_denies_quality_bypass", parsed is not None and parsed["hookSpecificOutput"]["decision"].get("behavior") == "deny", [], ["dae_guard.py permission-request"]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_feature(root)
        all_evidence(root)
        evidence(
            root,
            "crap",
            status="FAIL",
            tool="crap-analyzer",
            coverage_source="coverage.xml",
            thresholds={"max_crap_score": 30, "warn_crap_score": 20, "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded", "max_high_risk_findings": 0},
            summary={"changed_functions": 1, "max_crap_score": 45.0, "high_risk_findings": 1},
        )
        (root / ".engineer" / "quality-state.json").write_text('{"version":1,"quality_dirty":true,"dirty_since":"2026-05-22T00:00:00Z","active_feature":"001-demo","changed_files":["src/app.py"],"required_evidence":["crap"]}\n', encoding="utf-8")
        code, parsed, _ = run_guard("quality-verify", {}, root)
        results.append(result("failing_crap_blocks_quality_verify", code == 1 and parsed is not None and "crap" in parsed.get("blocking_gates", []), [str(root / "features" / "001-demo" / "evidence" / "quality" / "crap.json")], ["dae_guard.py quality-verify"]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_feature(root)
        all_evidence(root)
        evidence(
            root,
            "crap",
            tool="crap-analyzer",
            thresholds={"max_crap_score": 30, "warn_crap_score": 20, "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded", "max_high_risk_findings": 0},
            summary={"changed_functions": 1, "max_crap_score": 8.0, "high_risk_findings": 0},
            findings=[],
        )
        (root / ".engineer" / "quality-state.json").write_text('{"version":1,"quality_dirty":true,"dirty_since":"2026-05-22T00:00:00Z","active_feature":"001-demo","changed_files":["src/app.py"],"required_evidence":["crap"]}\n', encoding="utf-8")
        code, parsed, _ = run_guard("quality-verify", {}, root)
        errors = "\n".join(parsed.get("gate_results", {}).get("crap", {}).get("errors", [])) if parsed else ""
        results.append(result("missing_coverage_rejected_in_strict_mode", code == 1 and "coverage_source" in errors, [str(root / "features" / "001-demo" / "evidence" / "quality" / "crap.json")], ["dae_guard.py quality-verify"]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_feature(root)
        all_evidence(root)
        evidence(
            root,
            "crap",
            tool="crap-analyzer",
            coverage_source="coverage.xml",
            generated_at="2026-05-21T00:00:00Z",
            thresholds={"max_crap_score": 30, "warn_crap_score": 20, "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded", "max_high_risk_findings": 0},
            summary={"changed_functions": 1, "max_crap_score": 8.0, "high_risk_findings": 0},
            findings=[],
        )
        (root / ".engineer" / "quality-state.json").write_text('{"version":1,"quality_dirty":true,"dirty_since":"2026-05-22T00:00:00Z","active_feature":"001-demo","changed_files":["src/app.py"],"required_evidence":["crap"]}\n', encoding="utf-8")
        code, parsed, _ = run_guard("quality-verify", {}, root)
        errors = "\n".join(parsed.get("gate_results", {}).get("crap", {}).get("errors", [])) if parsed else ""
        results.append(result("stale_evidence_rejected", code == 1 and "stale" in errors, [str(root / "features" / "001-demo" / "evidence" / "quality" / "crap.json")], ["dae_guard.py quality-verify"]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_feature(root)
        evidence(
            root,
            "crap",
            tool="crap-analyzer",
            coverage_source="coverage.xml",
            thresholds={"max_crap_score": 30, "warn_crap_score": 20, "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded", "max_high_risk_findings": 0},
            summary={"changed_functions": 1, "max_crap_score": 8.0, "high_risk_findings": 0},
            findings=[],
        )
        (root / ".engineer" / "quality-state.json").write_text('{"version":1,"quality_dirty":true,"dirty_since":"2026-05-22T00:00:00Z","active_feature":"001-demo","changed_files":["src/app.py"]}\n', encoding="utf-8")
        code, parsed, _ = run_guard("quality-verify", {}, root)
        blockers = set(parsed.get("blocking_gates", [])) if parsed else set()
        results.append(result("passing_crap_does_not_unlock_other_gates", code == 1 and "crap" not in blockers and "acceptance" in blockers and "unit" in blockers, [str(root / "features" / "001-demo" / "evidence" / "quality" / "crap.json")], ["dae_guard.py quality-verify"]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_feature(root)
        all_evidence(root)
        evidence(
            root,
            "crap",
            status="WARN",
            tool="crap-analyzer",
            coverage_source="coverage.xml",
            thresholds={"max_crap_score": 30, "warn_crap_score": 20, "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded", "max_high_risk_findings": 0},
            summary={"changed_functions": 1, "max_crap_score": 22.0, "high_risk_findings": 1},
            findings=[{"file": "src/app.py", "symbol": "process", "crap_score": 22.0}],
        )
        (root / ".engineer" / "quality-state.json").write_text('{"version":1,"quality_dirty":true,"dirty_since":"2026-05-22T00:00:00Z","active_feature":"001-demo","changed_files":["src/app.py"]}\n', encoding="utf-8")
        code, parsed, _ = run_guard("quality-status", {}, root)
        required = set(parsed.get("required_gates", [])) if parsed else set()
        results.append(result("mutation_required_after_crap_warning", "mutation" in required, [str(root / "features" / "001-demo" / "evidence" / "quality" / "crap.json")], ["dae_guard.py quality-status"]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_feature(root)
        all_evidence(root)
        (root / ".engineer" / "quality-state.json").write_text(
            json.dumps({"version": 1, "quality_dirty": True, "dirty_since": "2026-05-22T00:00:00Z", "active_feature": "001-demo", "changed_files": ["src/app.py"], "required_evidence": ["acceptance", "unit", "crap", "arch", "refine", "branch_hygiene", "progress", "handoff", "duplicate_detection", "test_impact", "generated_acceptance_immutability"]})
            + "\n",
            encoding="utf-8",
        )
        code, parsed, _ = run_guard("quality-verify", {}, root)
        summary = root / "features" / "001-demo" / "evidence" / "quality" / "quality-gate-summary.json"
        results.append(result("passing_quality_summary_written", code == 0 and summary.exists(), [str(summary)], ["dae_guard.py quality-verify"]))
        code, parsed, _ = run_guard("pre-tool-use", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git commit -m demo"}}, root)
        results.append(result("git_commit_allowed_after_pass", parsed is None, [str(summary)], ["dae_guard.py pre-tool-use"]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".git").mkdir()
        (root / ".engineer").mkdir()
        (root / ".engineer" / "dae-quality-gates.json").write_text('{"schema_version":1,"gates":{"crap":{"mode":"warn"}}}\n', encoding="utf-8")
        code, parsed, _ = run_guard("validate-quality-config", {}, root)
        results.append(result("invalid_relaxation_rejected", code == 1 and parsed is not None, [str(root / ".engineer" / "dae-quality-gates.json")], ["dae_guard.py validate-quality-config"]))
        (root / ".engineer" / "dae-quality-gates.json").write_text(
            json.dumps({"schema_version": 1, "gates": {"crap": {"mode": "warn", "justification": "fixture", "scope": "fixture", "approved_by": "tester", "approved_at": "2026-05-22T00:00:00Z", "expires_at": "2026-06-22T00:00:00Z"}}})
            + "\n",
            encoding="utf-8",
        )
        code, parsed, _ = run_guard("validate-quality-config", {}, root)
        results.append(result("audited_relaxation_allowed", code == 0 and parsed is not None, [str(root / ".engineer" / "dae-quality-gates.json")], ["dae_guard.py validate-quality-config"]))

    matrix = {"schema_version": 1, "results": results}
    matrix_path = reports / "quality-gate-matrix.json"
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL", "matrix": str(matrix_path)}, indent=2))
    return 0 if all(r["status"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
