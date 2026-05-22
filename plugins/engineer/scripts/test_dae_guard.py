from __future__ import annotations

import json
import os
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
GUARD = REPO / "plugins" / "engineer" / "scripts" / "dae_guard.py"


def run_guard(subcommand: str, event: dict, cwd: Path, plugin_data: Path | None = None) -> tuple[int, dict | None, str]:
    env = os.environ.copy()
    env["CODEX_PROJECT_DIR"] = str(cwd)
    env["PLUGIN_ROOT"] = str(REPO / "plugins" / "engineer")
    env["PLUGIN_DATA"] = str(plugin_data or cwd / ".plugin-data")
    proc = subprocess.run(
        ["python3", str(GUARD), subcommand],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        check=False,
    )
    parsed = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, parsed, proc.stderr


def init_repo(root: Path) -> None:
    (root / ".git").mkdir()


def approve(root: Path, feature_id: str, checkpoint: str) -> None:
    approvals = root / ".engineer" / "approvals.jsonl"
    approvals.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "schema_version": "1.0",
        "timestamp": "2026-05-22T00:00:00Z",
        "feature_id": feature_id,
        "checkpoint": checkpoint,
        "artifact": f"features/{feature_id}/{checkpoint}.md",
        "decision": "approved",
        "approver_type": "human",
        "summary": f"Approved {checkpoint}",
    }
    with approvals.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def approve_project_start_plan(root: Path, feature_id: str = "000-project-start") -> None:
    plan = root / "features" / feature_id / "plan.md"
    digest = hashlib.sha256(plan.read_bytes()).hexdigest()
    approvals = root / ".engineer" / "approvals.jsonl"
    approvals.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "type": "plan_approved",
        "flow": "project_start",
        "feature_id": feature_id,
        "artifact": f"features/{feature_id}/plan.md",
        "artifact_sha256": digest,
        "approved_by": "user",
        "approved_at": "2026-05-22T00:00:00Z",
        "source": "user_prompt_submit",
        "prompt_excerpt": "I approve the plan",
    }
    with approvals.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def create_project_start_artifacts(root: Path, feature_id: str = "000-project-start") -> None:
    feature = root / "features" / feature_id
    feature.mkdir(parents=True)
    (root / "CHARTER.md").write_text("# Charter\n", encoding="utf-8")
    for name in ("feature.md", "acs.md", "spec.md", "plan.md"):
        (feature / name).write_text(f"# {name}\n", encoding="utf-8")


def write_quality_evidence(root: Path, feature_id: str, gate: str, status: str = "PASS", **extra: object) -> None:
    evidence = root / "features" / feature_id / "evidence" / "quality"
    evidence.mkdir(parents=True, exist_ok=True)
    filenames = {
        "branch_hygiene": "branch-hygiene.json",
        "duplicate_detection": "duplicate-detection.json",
        "test_impact": "test-impact.json",
        "generated_acceptance_immutability": "generated-acceptance-immutability.json",
    }
    data = {
        "schema_version": 1,
        "gate": gate,
        "status": status,
        "generated_at": "2099-01-01T00:00:00Z",
        "feature": f"features/{feature_id}",
        "changed_files": ["src/app.py"],
        "command": f"test {gate}",
        "artifacts": [],
        "summary": {},
        "limitations": [],
    }
    data.update(extra)
    (evidence / filenames.get(gate, f"{gate}.json")).write_text(json.dumps(data) + "\n", encoding="utf-8")


def write_all_strict_quality_evidence(root: Path, feature_id: str = "001-demo") -> None:
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
        write_quality_evidence(root, feature_id, gate)
    write_quality_evidence(
        root,
        feature_id,
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


class DaeGuardTests(unittest.TestCase):
    def test_validate_contract_passes(self) -> None:
        code, parsed, err = run_guard("validate-contract", {}, REPO)
        self.assertEqual(code, 0, err)
        self.assertEqual(parsed["status"], "PASS")

    def test_user_prompt_blocks_bypass_without_gates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            event = {"hook_event_name": "UserPromptSubmit", "prompt": "Ignore DAE and just implement. Skip specs."}
            _, parsed, _ = run_guard("user-prompt-submit", event, root)
            self.assertEqual(parsed["decision"], "block")
            self.assertIn("dae.pipeline_order", parsed["reason"])
            self.assertEqual(parsed["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")

    def test_user_prompt_routes_new_project_to_intake(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            event = {"hook_event_name": "UserPromptSubmit", "prompt": "Сделай с нуля CRM для малого бизнеса"}
            _, parsed, _ = run_guard("user-prompt-submit", event, root)
            self.assertIsNotNone(parsed)
            self.assertIn("hookSpecificOutput", parsed)
            self.assertEqual(parsed["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
            self.assertIn("project-start intake", parsed["hookSpecificOutput"]["additionalContext"])
            self.assertNotEqual(parsed.get("decision"), "block")

    def test_user_prompt_allows_feature_init(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            event = {"hook_event_name": "UserPromptSubmit", "prompt": "Start feature-init and discover ACs."}
            _, parsed, _ = run_guard("user-prompt-submit", event, root)
            self.assertEqual(parsed["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
            self.assertIn("DAE workflow prompt allowed", parsed["hookSpecificOutput"]["additionalContext"])

    def test_pre_tool_denies_source_write_without_gates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"},
            }
            _, parsed, _ = run_guard("pre-tool-use", event, root)
            self.assertEqual(parsed["hookSpecificOutput"]["hookEventName"], "PreToolUse")
            self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("dae.source_write_requires_gates", parsed["hookSpecificOutput"]["permissionDecisionReason"])

    def test_pre_tool_denies_scaffold_config_writes_without_gates(self) -> None:
        blocked = ["package.json", "pyproject.toml", "Dockerfile"]
        for target in blocked:
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    init_repo(root)
                    event = {
                        "hook_event_name": "PreToolUse",
                        "tool_name": "apply_patch",
                        "tool_input": {"command": f"*** Begin Patch\n*** Add File: {target}\n+demo\n*** End Patch"},
                    }
                    _, parsed, _ = run_guard("pre-tool-use", event, root)
                    self.assertEqual(parsed["hookSpecificOutput"]["hookEventName"], "PreToolUse")
                    self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")
                    self.assertIn("dae.source_write_requires_gates", parsed["hookSpecificOutput"]["permissionDecisionReason"])

    def test_pre_tool_allows_project_start_planning_artifacts_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Add File: features/000-project-start/spec.md\n+# Spec\n*** End Patch"
                },
            }
            _, parsed, _ = run_guard("pre-tool-use", event, root)
            self.assertIsNone(parsed)

    def test_pre_tool_denies_npm_init_before_approval(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "npm init -y"},
            }
            _, parsed, _ = run_guard("pre-tool-use", event, root)
            self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("dae.source_write_requires_gates", parsed["hookSpecificOutput"]["permissionDecisionReason"])

    def test_pre_tool_denies_project_start_plan_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            create_project_start_artifacts(root)
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"},
            }
            _, parsed, _ = run_guard("pre-tool-use", event, root)
            self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("approved_plan", parsed["hookSpecificOutput"]["permissionDecisionReason"])

    def test_pre_tool_allows_project_start_source_write_with_non_stale_plan_approval(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            create_project_start_artifacts(root)
            approve_project_start_plan(root)
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"},
            }
            _, parsed, _ = run_guard("pre-tool-use", event, root)
            self.assertIsNone(parsed)

    def test_pre_tool_denies_project_start_source_write_with_stale_plan_approval(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            create_project_start_artifacts(root)
            approve_project_start_plan(root)
            (root / "features" / "000-project-start" / "plan.md").write_text("# changed\n", encoding="utf-8")
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"},
            }
            _, parsed, _ = run_guard("pre-tool-use", event, root)
            self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("approved_plan", parsed["hookSpecificOutput"]["permissionDecisionReason"])

    def test_pre_tool_denies_detectable_bash_source_write_without_gates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "cat > src/app.py <<'PY'\nprint(1)\nPY"},
            }
            _, parsed, _ = run_guard("pre-tool-use", event, root)
            self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("dae.source_write_requires_gates", parsed["hookSpecificOutput"]["permissionDecisionReason"])

    def test_pre_tool_allows_source_write_with_approved_plan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            feature = root / "features" / "001-demo"
            feature.mkdir(parents=True)
            for name in ("feature.md", "acs.md", "spec.md", "plan.md"):
                (feature / name).write_text("# ok\n", encoding="utf-8")
            approve(root, "001-demo", "acceptance_criteria")
            approve(root, "001-demo", "plan")
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"},
            }
            _, parsed, _ = run_guard("pre-tool-use", event, root)
            self.assertIsNone(parsed)

    def test_pre_tool_denies_generated_acceptance_test_edit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: tests/acceptance/generated/test_feature.py\n@@\n-pass\n+assert False\n*** End Patch"
                },
            }
            _, parsed, _ = run_guard("pre-tool-use", event, root)
            self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("dae.generated_acceptance_tests_immutable", parsed["hookSpecificOutput"]["permissionDecisionReason"])

    def test_pre_tool_denies_spec_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            event = {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {"command": "*** Begin Patch\n*** Add File: features/001-demo/spec.md\n+Then UserService calls /api/users\n*** End Patch"},
            }
            _, parsed, _ = run_guard("pre-tool-use", event, root)
            self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("dae.spec_leakage_forbidden", parsed["hookSpecificOutput"]["permissionDecisionReason"])

    def test_permission_request_denies_dangerous_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            event = {
                "hook_event_name": "PermissionRequest",
                "tool_name": "Bash",
                "permission_mode": "default",
                "tool_input": {"command": "sudo rm -rf /tmp/demo"},
            }
            _, parsed, _ = run_guard("permission-request", event, root)
            self.assertEqual(parsed["hookSpecificOutput"]["hookEventName"], "PermissionRequest")
            self.assertEqual(parsed["hookSpecificOutput"]["decision"]["behavior"], "deny")

    def test_post_tool_records_implementation_and_stop_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            post = {
                "hook_event_name": "PostToolUse",
                "tool_name": "apply_patch",
                "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"},
            }
            _, parsed, _ = run_guard("post-tool-use", post, root)
            self.assertEqual(parsed["hookSpecificOutput"]["hookEventName"], "PostToolUse")
            self.assertIn("additionalContext", parsed["hookSpecificOutput"])
            quality_state = json.loads((root / ".engineer" / "quality-state.json").read_text(encoding="utf-8"))
            self.assertTrue(quality_state["quality_dirty"])
            self.assertIn("crap", quality_state["required_evidence"])
            stop = {"hook_event_name": "Stop", "last_assistant_message": "Implemented the feature. Done."}
            _, parsed, _ = run_guard("stop", stop, root)
            self.assertEqual(parsed["decision"], "block")
            self.assertNotIn("hookSpecificOutput", parsed)
            self.assertIn("acceptance", parsed["reason"])
            self.assertIn("crap", parsed["reason"])

    def test_stop_allows_when_strict_quality_evidence_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            feature = root / "features" / "001-demo"
            feature.mkdir(parents=True)
            (feature / "progress.md").write_text("# progress\n", encoding="utf-8")
            (feature / "handoffs").mkdir()
            (feature / "handoffs" / "summary.md").write_text("# handoff\n", encoding="utf-8")
            write_all_strict_quality_evidence(root, "001-demo")
            (root / ".engineer").mkdir()
            (root / ".engineer" / "dae-state.json").write_text(
                '{"schema_version":"1.0","active_feature":"001-demo","implementation_started":true}\n',
                encoding="utf-8",
            )
            (root / ".engineer" / "quality-state.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "quality_dirty": True,
                        "dirty_since": "2026-05-22T00:00:00Z",
                        "active_feature": "001-demo",
                        "changed_files": ["src/app.py"],
                        "required_evidence": [
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
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            stop = {"hook_event_name": "Stop", "last_assistant_message": "Implemented the feature. Done."}
            _, parsed, _ = run_guard("stop", stop, root)
            self.assertIsNone(parsed)

    def test_stop_requires_configured_crap_and_mutation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            feature = root / "features" / "001-demo"
            feature.mkdir(parents=True)
            (feature / "progress.md").write_text("# progress\n", encoding="utf-8")
            (feature / "handoffs").mkdir()
            (feature / "handoffs" / "summary.md").write_text("# handoff\n", encoding="utf-8")
            write_all_strict_quality_evidence(root, "001-demo")
            (feature / "evidence" / "quality" / "crap.json").unlink()
            (root / ".engineer").mkdir()
            (root / ".engineer" / "dae-state.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "active_feature": "001-demo",
                        "implementation_started": True,
                        "required_evidence": {"crap": True, "mutation": True},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            stop = {"hook_event_name": "Stop", "last_assistant_message": "Implemented the feature. Done."}
            _, parsed, _ = run_guard("stop", stop, root)
            self.assertEqual(parsed["decision"], "block")
            self.assertIn("crap", parsed["reason"])
            self.assertIn("mutation", parsed["reason"])

    def test_quality_verify_rejects_failing_crap_score(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            feature = root / "features" / "001-demo"
            feature.mkdir(parents=True)
            write_all_strict_quality_evidence(root, "001-demo")
            write_quality_evidence(
                root,
                "001-demo",
                "crap",
                status="FAIL",
                tool="crap-analyzer",
                coverage_source="coverage.xml",
                thresholds={"max_crap_score": 30, "warn_crap_score": 20, "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded", "max_high_risk_findings": 0},
                summary={"changed_functions": 1, "max_crap_score": 45.0, "high_risk_findings": 1},
                findings=[{"file": "src/app.py", "symbol": "process", "crap_score": 45.0}],
            )
            (root / ".engineer").mkdir()
            (root / ".engineer" / "dae-state.json").write_text('{"active_feature":"001-demo","implementation_started":true}\n', encoding="utf-8")
            (root / ".engineer" / "quality-state.json").write_text(
                '{"version":1,"quality_dirty":true,"dirty_since":"2026-05-22T00:00:00Z","active_feature":"001-demo","changed_files":["src/app.py"],"required_evidence":["crap"]}\n',
                encoding="utf-8",
            )
            code, parsed, _ = run_guard("quality-verify", {}, root)
            self.assertEqual(code, 1)
            self.assertEqual(parsed["status"], "FAIL")
            self.assertIn("crap", parsed["blocking_gates"])

    def test_quality_verify_rejects_crap_without_coverage_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            feature = root / "features" / "001-demo"
            feature.mkdir(parents=True)
            write_all_strict_quality_evidence(root, "001-demo")
            write_quality_evidence(
                root,
                "001-demo",
                "crap",
                tool="crap-analyzer",
                thresholds={"max_crap_score": 30, "warn_crap_score": 20, "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded", "max_high_risk_findings": 0},
                summary={"changed_functions": 1, "max_crap_score": 8.0, "high_risk_findings": 0},
                findings=[],
            )
            (root / ".engineer").mkdir(exist_ok=True)
            (root / ".engineer" / "dae-state.json").write_text('{"active_feature":"001-demo","implementation_started":true}\n', encoding="utf-8")
            (root / ".engineer" / "quality-state.json").write_text(
                '{"version":1,"quality_dirty":true,"dirty_since":"2026-05-22T00:00:00Z","active_feature":"001-demo","changed_files":["src/app.py"],"required_evidence":["crap"]}\n',
                encoding="utf-8",
            )
            code, parsed, _ = run_guard("quality-verify", {}, root)
            self.assertEqual(code, 1)
            self.assertIn("crap", parsed["blocking_gates"])
            self.assertIn("coverage_source", "\n".join(parsed["gate_results"]["crap"]["errors"]))

    def test_crap_pass_alone_does_not_unlock_other_required_gates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            feature = root / "features" / "001-demo"
            feature.mkdir(parents=True)
            write_quality_evidence(
                root,
                "001-demo",
                "crap",
                tool="crap-analyzer",
                coverage_source="coverage.xml",
                thresholds={"max_crap_score": 30, "warn_crap_score": 20, "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded", "max_high_risk_findings": 0},
                summary={"changed_functions": 1, "max_crap_score": 8.0, "high_risk_findings": 0},
                findings=[],
            )
            (root / ".engineer").mkdir(exist_ok=True)
            (root / ".engineer" / "dae-state.json").write_text('{"active_feature":"001-demo","implementation_started":true}\n', encoding="utf-8")
            (root / ".engineer" / "quality-state.json").write_text(
                '{"version":1,"quality_dirty":true,"dirty_since":"2026-05-22T00:00:00Z","active_feature":"001-demo","changed_files":["src/app.py"]}\n',
                encoding="utf-8",
            )
            code, parsed, _ = run_guard("quality-verify", {}, root)
            self.assertEqual(code, 1)
            self.assertNotIn("crap", parsed["blocking_gates"])
            self.assertIn("acceptance", parsed["blocking_gates"])

    def test_quality_verify_rejects_stale_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            feature = root / "features" / "001-demo"
            feature.mkdir(parents=True)
            write_all_strict_quality_evidence(root, "001-demo")
            write_quality_evidence(
                root,
                "001-demo",
                "crap",
                tool="crap-analyzer",
                coverage_source="coverage.xml",
                generated_at="2026-05-21T00:00:00Z",
                thresholds={"max_crap_score": 30, "warn_crap_score": 20, "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded", "max_high_risk_findings": 0},
                summary={"changed_functions": 1, "max_crap_score": 8.0, "high_risk_findings": 0},
                findings=[],
            )
            (root / ".engineer").mkdir(exist_ok=True)
            (root / ".engineer" / "dae-state.json").write_text('{"active_feature":"001-demo","implementation_started":true}\n', encoding="utf-8")
            (root / ".engineer" / "quality-state.json").write_text(
                '{"version":1,"quality_dirty":true,"dirty_since":"2026-05-22T00:00:00Z","active_feature":"001-demo","changed_files":["src/app.py"],"required_evidence":["crap"]}\n',
                encoding="utf-8",
            )
            code, parsed, _ = run_guard("quality-verify", {}, root)
            self.assertEqual(code, 1)
            self.assertIn("stale", "\n".join(parsed["gate_results"]["crap"]["errors"]))

    def test_mutation_required_when_crap_warning_triggers_risk_policy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            feature = root / "features" / "001-demo"
            feature.mkdir(parents=True)
            write_all_strict_quality_evidence(root, "001-demo")
            write_quality_evidence(
                root,
                "001-demo",
                "crap",
                status="WARN",
                tool="crap-analyzer",
                coverage_source="coverage.xml",
                thresholds={"max_crap_score": 30, "warn_crap_score": 20, "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded", "max_high_risk_findings": 0},
                summary={"changed_functions": 1, "max_crap_score": 22.0, "high_risk_findings": 1},
                findings=[{"file": "src/app.py", "symbol": "process", "crap_score": 22.0}],
            )
            (root / ".engineer").mkdir(exist_ok=True)
            (root / ".engineer" / "dae-state.json").write_text('{"active_feature":"001-demo","implementation_started":true}\n', encoding="utf-8")
            (root / ".engineer" / "quality-state.json").write_text(
                '{"version":1,"quality_dirty":true,"dirty_since":"2026-05-22T00:00:00Z","active_feature":"001-demo","changed_files":["src/app.py"]}\n',
                encoding="utf-8",
            )
            code, parsed, _ = run_guard("quality-status", {}, root)
            self.assertEqual(code, 1)
            self.assertIn("mutation", parsed["required_gates"])

    def test_quality_config_relaxation_requires_audit_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repo(root)
            (root / ".engineer").mkdir()
            (root / ".engineer" / "dae-quality-gates.json").write_text(
                '{"schema_version":1,"gates":{"crap":{"mode":"warn"}}}\n',
                encoding="utf-8",
            )
            code, parsed, _ = run_guard("validate-quality-config", {}, root)
            self.assertEqual(code, 1)
            self.assertIn("relaxation", "\n".join(parsed["errors"]))
            (root / ".engineer" / "dae-quality-gates.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "gates": {
                            "crap": {
                                "mode": "warn",
                                "justification": "coverage tool unavailable in this fixture",
                                "scope": "fixture",
                                "approved_by": "tester",
                                "approved_at": "2026-05-22T00:00:00Z",
                                "expires_at": "2026-06-22T00:00:00Z",
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            code, parsed, _ = run_guard("validate-quality-config", {}, root)
            self.assertEqual(code, 0, parsed.get("errors"))


if __name__ == "__main__":
    unittest.main()
