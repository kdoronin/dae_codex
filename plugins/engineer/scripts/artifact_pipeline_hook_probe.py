#!/usr/bin/env python3
"""Synthetic probes for artifact/state/evidence-gated DAE enforcement."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
GUARD = REPO / "plugins" / "engineer" / "scripts" / "dae_guard.py"


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_guard(subcommand: str, event: dict[str, Any], root: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["CODEX_PROJECT_DIR"] = str(root)
    env["PLUGIN_ROOT"] = str(REPO / "plugins" / "engineer")
    env["PLUGIN_DATA"] = str(root / ".plugin-data")
    proc = subprocess.run(
        [sys.executable, str(GUARD), subcommand],
        input=json.dumps(event, ensure_ascii=False),
        text=True,
        cwd=str(root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    parsed = None
    if proc.stdout.strip():
        parsed = json.loads(proc.stdout)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "parsed_stdout": parsed,
    }


def decision(result: dict[str, Any]) -> str:
    out = result.get("parsed_stdout")
    if not isinstance(out, dict):
        return "allow"
    if out.get("decision") == "block":
        return "deny"
    hso = out.get("hookSpecificOutput")
    if isinstance(hso, dict):
        if hso.get("permissionDecision") == "deny":
            return "deny"
        nested = hso.get("decision")
        if isinstance(nested, dict) and nested.get("behavior") == "deny":
            return "deny"
        if hso.get("additionalContext"):
            return "context"
    return str(out.get("decision") or "allow")


def init_repo(root: Path) -> None:
    (root / ".git").mkdir(exist_ok=True)


def create_artifacts(root: Path, approved: bool = False) -> None:
    init_repo(root)
    feature = root / "features" / "001-demo"
    feature.mkdir(parents=True, exist_ok=True)
    for name in ("feature.md", "acs.md", "spec.md", "plan.md"):
        write(feature / name, f"# {name}\n")
    if approved:
        approvals = root / ".engineer" / "approvals.jsonl"
        for checkpoint in ("acceptance_criteria", "plan"):
            event = {
                "schema_version": "1.0",
                "timestamp": now_iso(),
                "feature_id": "001-demo",
                "checkpoint": checkpoint,
                "artifact": f"features/001-demo/{checkpoint}.md",
                "decision": "approved",
                "approver_type": "human",
            }
            approvals.parent.mkdir(parents=True, exist_ok=True)
            with approvals.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def create_project_start_artifacts(root: Path, approved: bool = False) -> None:
    init_repo(root)
    write(root / "CHARTER.md", "# Charter\n")
    feature = root / "features" / "000-project-start"
    for name in ("feature.md", "acs.md", "spec.md", "plan.md"):
        write(feature / name, f"# {name}\n")
    write(root / ".engineer" / "project-start-state.json", json.dumps({
        "version": 1,
        "flow": "project_start",
        "state": "PLAN_DRAFTED" if not approved else "PLAN_APPROVED",
        "feature_id": "000-project-start",
        "artifacts": {
            "charter": "CHARTER.md",
            "feature": "features/000-project-start/feature.md",
            "acs": "features/000-project-start/acs.md",
            "spec": "features/000-project-start/spec.md",
            "plan": "features/000-project-start/plan.md",
            "progress": "features/000-project-start/progress.md"
        }
    }, indent=2) + "\n")
    if approved:
        plan = root / "features" / "000-project-start" / "plan.md"
        write(root / ".engineer" / "approvals.jsonl", json.dumps({
            "type": "plan_approved",
            "flow": "project_start",
            "feature_id": "000-project-start",
            "artifact": "features/000-project-start/plan.md",
            "artifact_sha256": sha256(plan),
            "approved_by": "user",
            "approved_at": now_iso(),
            "source": "fixture",
        }, ensure_ascii=False) + "\n")


def evidence(root: Path, gate: str, status: str = "PASS", **extra: Any) -> None:
    names = {
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
    write(root / "features" / "001-demo" / "evidence" / "quality" / names.get(gate, f"{gate}.json"), json.dumps(data, indent=2) + "\n")


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


def matrix_item(item_id: str, status: str, expected: str, actual: str, evidence_paths: list[str]) -> dict[str, Any]:
    return {
        "id": item_id,
        "status": status,
        "expected": expected,
        "actual": actual,
        "evidence": evidence_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".dae-artifact-gated-pipeline")
    args = parser.parse_args()
    out_root = (REPO / args.out).resolve()
    logs = out_root / "logs"
    reports = out_root / "reports"
    logs.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    scenarios: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_repo(root)
        event = {"hook_event_name": "UserPromptSubmit", "prompt": "Сделай с нуля CRM", "cwd": str(root)}
        result = run_guard("user-prompt-submit", event, root)
        log = logs / "scenario-01-user-prompt-crm.json"
        write(log, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        scenarios.append(matrix_item(
            "crm_prompt_routes_context",
            "PASS" if decision(result) == "context" else "FAIL",
            "UserPromptSubmit adds intake context and does not block",
            decision(result),
            [str(log.relative_to(REPO))],
        ))
        source = run_guard("pre-tool-use", {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"}, "cwd": str(root)}, root)
        artifact = run_guard("pre-tool-use", {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch\n*** Add File: features/000-project-start/spec.md\n+# Spec\n*** End Patch"}, "cwd": str(root)}, root)
        log = logs / "scenario-02-artifact-vs-source.json"
        write(log, json.dumps({"source": source, "artifact": artifact}, ensure_ascii=False, indent=2) + "\n")
        actual = f"source={decision(source)} artifact={decision(artifact)}"
        scenarios.append(matrix_item(
            "source_denied_artifact_allowed_before_plan",
            "PASS" if decision(source) == "deny" and decision(artifact) == "allow" else "FAIL",
            "Source write is denied; planning artifact write is allowed",
            actual,
            [str(log.relative_to(REPO))],
        ))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_repo(root)
        result = run_guard("user-prompt-submit", {"hook_event_name": "UserPromptSubmit", "prompt": "/goal Implement CRAP quality gates and prevent bypass skip ignore disable hooks quality ATDD tests", "cwd": str(root)}, root)
        log = logs / "scenario-03-keyword-goal.json"
        write(log, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        scenarios.append(matrix_item(
            "goal_with_policy_words_not_blocked",
            "PASS" if decision(result) == "context" else "FAIL",
            "Prompt with policy words receives context, not decision:block",
            decision(result),
            [str(log.relative_to(REPO))],
        ))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        create_project_start_artifacts(root, approved=False)
        result = run_guard("pre-tool-use", {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"}, "cwd": str(root)}, root)
        log = logs / "scenario-04-plan-not-approved.json"
        write(log, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        scenarios.append(matrix_item("plan_not_approved_denies_source", "PASS" if decision(result) == "deny" else "FAIL", "Implementation write denied without plan approval", decision(result), [str(log.relative_to(REPO))]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        create_project_start_artifacts(root, approved=True)
        result = run_guard("pre-tool-use", {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"}, "cwd": str(root)}, root)
        log = logs / "scenario-05-plan-approved.json"
        write(log, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        scenarios.append(matrix_item("plan_approved_allows_source", "PASS" if decision(result) == "allow" else "FAIL", "Implementation write allowed after non-stale approval", decision(result), [str(log.relative_to(REPO))]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        create_artifacts(root, approved=True)
        post = run_guard("post-tool-use", {"hook_event_name": "PostToolUse", "tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"}, "cwd": str(root)}, root)
        quality = json.loads((root / ".engineer" / "quality-state.json").read_text(encoding="utf-8"))
        log = logs / "scenario-06-quality-dirty.json"
        write(log, json.dumps({"post": post, "quality_state": quality}, ensure_ascii=False, indent=2) + "\n")
        ok = bool(quality.get("quality_dirty")) and {"acceptance", "unit", "crap"}.issubset(set(quality.get("required_evidence", [])))
        scenarios.append(matrix_item("implementation_edit_marks_quality_dirty", "PASS" if ok else "FAIL", "PostToolUse marks dirty and requires evidence", json.dumps({"quality_dirty": quality.get("quality_dirty"), "required": quality.get("required_evidence")}), [str(log.relative_to(REPO))]))
        stop = run_guard("stop", {"hook_event_name": "Stop", "last_assistant_message": "Done.", "cwd": str(root)}, root)
        log = logs / "scenario-07-stop-before-crap.json"
        write(log, json.dumps(stop, ensure_ascii=False, indent=2) + "\n")
        scenarios.append(matrix_item("stop_before_quality_evidence_denied", "PASS" if decision(stop) == "deny" and "crap" in stop.get("stdout", "") else "FAIL", "Stop denies completion before CRAP and other evidence", decision(stop), [str(log.relative_to(REPO))]))
        commit = run_guard("pre-tool-use", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git commit -m demo"}, "cwd": str(root)}, root)
        log = logs / "scenario-08-commit-dirty.json"
        write(log, json.dumps(commit, ensure_ascii=False, indent=2) + "\n")
        scenarios.append(matrix_item("commit_while_dirty_denied", "PASS" if decision(commit) == "deny" else "FAIL", "Commit denied while quality is dirty", decision(commit), [str(log.relative_to(REPO))]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        create_artifacts(root, approved=True)
        all_evidence(root)
        write(root / ".engineer" / "dae-state.json", '{"schema_version":"1.0","active_feature":"001-demo","implementation_started":true}\n')
        write(root / ".engineer" / "quality-state.json", json.dumps({
            "version": 1,
            "quality_dirty": True,
            "dirty_since": "2026-05-22T00:00:00Z",
            "active_feature": "001-demo",
            "changed_files": ["src/app.py"],
            "required_evidence": ["acceptance", "unit", "crap", "arch", "refine", "branch_hygiene", "progress", "handoff", "duplicate_detection", "test_impact", "generated_acceptance_immutability"]
        }) + "\n")
        result = run_guard("stop", {"hook_event_name": "Stop", "last_assistant_message": "Done.", "cwd": str(root)}, root)
        log = logs / "scenario-09-stop-after-evidence.json"
        write(log, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        scenarios.append(matrix_item("stop_after_all_fresh_evidence_allowed", "PASS" if decision(result) == "allow" else "FAIL", "Stop allows after all fresh strict evidence", decision(result), [str(log.relative_to(REPO))]))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_repo(root)
        write(root / ".engineer" / "dae-quality-gates.json", '{"schema_version":1,"gates":{"crap":{"mode":"warn"}}}\n')
        invalid = run_guard("validate-quality-config", {}, root)
        write(root / ".engineer" / "dae-quality-gates.json", json.dumps({
            "schema_version": 1,
            "gates": {
                "crap": {
                    "mode": "warn",
                    "justification": "fixture relaxation",
                    "scope": "artifact probe",
                    "approved_by": "tester",
                    "approved_at": "2026-05-22T00:00:00Z",
                    "expires_at": "2026-06-22T00:00:00Z"
                }
            }
        }) + "\n")
        valid = run_guard("validate-quality-config", {}, root)
        log = logs / "scenario-10-overrides.json"
        write(log, json.dumps({"invalid": invalid, "valid": valid}, ensure_ascii=False, indent=2) + "\n")
        actual = f"invalid={invalid['returncode']} valid={valid['returncode']}"
        scenarios.append(matrix_item("policy_override_audit_required", "PASS" if invalid["returncode"] == 1 and valid["returncode"] == 0 else "FAIL", "Invalid relaxation rejected; audited relaxation accepted", actual, [str(log.relative_to(REPO))]))

    verdict = "PASS" if all(item["status"] in {"PASS", "NA"} for item in scenarios) else "FAIL"
    matrix = {"verdict": verdict, "generated_at": now_iso(), "scenarios": scenarios}
    matrix_path = reports / "pipeline-transition-matrix.json"
    write(matrix_path, json.dumps(matrix, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "matrix": str(matrix_path.relative_to(REPO))}, ensure_ascii=False, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
