# Plan

Architecture:
- Keep Codex-native plugin hooks as the primary runtime surface.
- Use `plugins/engineer/scripts/dae_guard.py` as the central state/action/evidence evaluator.
- Keep prompt handling non-blocking and move hard enforcement to tool, permission, quality, and stop events.
- Store strict configurable defaults in machine-readable guardrail JSON.

Implementation sequence:
1. Replace prompt hard-block branches with context-only routing.
2. Keep source/write/finalization denials in `PreToolUse` and `PermissionRequest`.
3. Keep dirty-state and evidence requirements in `PostToolUse` and `Stop`.
4. Add policy/state schemas and synthetic artifact-gated fixture probes.
5. Update docs, hook status messages, tests, and installer/runtime validation.
6. Run unit tests, static audits, schema validation, hook probes, and installer verification.

Testing plan:
- Unit tests for no-keyword prompt behavior, source write denial/allowance, dirty-state marking, stop gates, CRAP gates, stale evidence, and audited override validation.
- Synthetic hook probes for prompt routing, artifact writes, implementation writes, approval, dirty quality state, stop gates, release gates, and overrides.
- Static audit for keyword-blocking anti-patterns.

Quality gates:
- Acceptance stream: synthetic hook matrices.
- Unit stream: `python3 -m unittest discover plugins/engineer/scripts`.
- CRAP: required by default after implementation-affecting edits.
- Architecture/refine/progress/handoff: required evidence gates in strict config.
- Mutation: required when configured or risk-triggered.

Risks:
- Personal non-managed hooks can be disabled by users; docs must describe this limitation.
- Static keyword audits may warn when prompt and block logic share a file even if the runtime path is safe.

Rollback:
- Revert the guard, contract, docs, and probe changes as a single commit if hook output contracts fail.

Approval:
- Delegated repo-maintenance approval is provided by the user `/goal` for this bounded repair and validation loop.
