# Feature 001 artifact-gated pipeline

Goal: replace DAE prompt-keyword blocking with artifact, state, and evidence-gated runtime enforcement for the Codex plugin.

Actors:
- Codex agent running with DAE hooks.
- Human maintainer approving charter and architecture decisions.

Scope:
- `UserPromptSubmit` becomes a non-blocking router and context injector.
- `PreToolUse`, `PostToolUse`, `PermissionRequest`, and `Stop` enforce machine-readable state, artifact, approval, freshness, and quality gates.
- Strict quality defaults require ATDD acceptance evidence, unit evidence, CRAP evidence, architecture/refine checks, progress, handoff, duplicate detection, test impact, generated acceptance immutability, and mutation when configured or risk-triggered.
- Installer, docs, probes, tests, and reports reflect the artifact-gated model.

Non-goals:
- Making user-editable personal hooks impossible to disable.
- Replacing Codex managed/admin hook enforcement.
- Running expensive analyzers on every edit.

Assumptions:
- The user `/goal` is delegated repo-maintenance approval for this repair because it is self-contained, includes validation, and defines stop conditions.
- Hook runtime may require the installer bridge in `~/.codex/hooks.json` on current Codex releases.

Open questions:
- None for this repair.
