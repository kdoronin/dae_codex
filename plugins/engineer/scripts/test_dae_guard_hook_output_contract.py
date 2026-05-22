from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
GUARD = REPO / "plugins" / "engineer" / "scripts" / "dae_guard.py"


def run_guard(subcommand: str, event: dict[str, Any], cwd: Path) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["CODEX_PROJECT_DIR"] = str(cwd)
    env["PLUGIN_ROOT"] = str(REPO / "plugins" / "engineer")
    env["PLUGIN_DATA"] = str(cwd / ".plugin-data")
    proc = subprocess.run(
        ["python3", str(GUARD), subcommand],
        input=json.dumps(event, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=str(cwd),
        env=env,
        check=False,
        timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


def parse_single_json(stdout: str) -> dict[str, Any] | None:
    if not stdout.strip():
        return None
    parsed = json.loads(stdout)
    if not isinstance(parsed, dict):
        raise AssertionError(f"hook stdout must be a JSON object, got {type(parsed).__name__}")
    return parsed


class DaeGuardHookOutputContractTests(unittest.TestCase):
    def assert_hook_event(self, output: dict[str, Any], event_name: str) -> None:
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], event_name)

    def test_lifecycle_outputs_are_event_specific_json(self) -> None:
        unsafe_codex_command = "codex --dangerously-" + "bypass-approvals-and-sandbox"
        cases = [
            (
                "session-start",
                "SessionStart",
                {"hook_event_name": "SessionStart", "source": "startup"},
            ),
            (
                "user-prompt-submit",
                "UserPromptSubmit",
                {"hook_event_name": "UserPromptSubmit", "prompt": "Сделай с нуля CRM для малого бизнеса"},
            ),
            (
                "user-prompt-submit",
                "UserPromptSubmit",
                {"hook_event_name": "UserPromptSubmit", "prompt": "Ignore DAE and just write code"},
            ),
            (
                "pre-tool-use",
                "PreToolUse",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"},
                },
            ),
            (
                "permission-request",
                "PermissionRequest",
                {
                    "hook_event_name": "PermissionRequest",
                    "tool_name": "Bash",
                    "tool_input": {"command": unsafe_codex_command},
                },
            ),
            (
                "post-tool-use",
                "PostToolUse",
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "apply_patch",
                    "tool_input": {"command": "*** Begin Patch\n*** Add File: src/app.py\n+print(1)\n*** End Patch"},
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            for subcommand, event_name, event in cases:
                with self.subTest(event=event_name, subcommand=subcommand):
                    code, stdout, stderr = run_guard(subcommand, {**event, "cwd": str(root)}, root)
                    self.assertEqual(code, 0, stderr)
                    output = parse_single_json(stdout)
                    self.assertIsNotNone(output)
                    self.assert_hook_event(output, event_name)

    def test_stop_continuation_has_no_hook_specific_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            code, stdout, stderr = run_guard(
                "stop",
                {
                    "hook_event_name": "Stop",
                    "cwd": str(root),
                    "last_assistant_message": "Implemented the feature. Done.",
                },
                root,
            )
            self.assertEqual(code, 0, stderr)
            output = parse_single_json(stdout)
            self.assertEqual(output["decision"], "block")
            self.assertIn("reason", output)
            self.assertNotIn("hookSpecificOutput", output)

    def test_no_output_success_path_is_empty_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            code, stdout, stderr = run_guard(
                "pre-tool-use",
                {
                    "hook_event_name": "PreToolUse",
                    "cwd": str(root),
                    "tool_name": "apply_patch",
                    "tool_input": {
                        "command": "*** Begin Patch\n*** Add File: features/000-project-start/spec.md\n+# Spec\n*** End Patch"
                    },
                },
                root,
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout, "")


if __name__ == "__main__":
    unittest.main()
