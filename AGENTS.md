# AGENTS.md

## Repository role

This repository packages Disciplined Agentic Engineering (DAE) as Codex CLI plugins, skills, hooks, custom agents, guardrail scripts, and documentation.

## Non-negotiable methodology contracts

- Preserve the DAE pipeline: charter → feature/Ready contract → ACs → Gherkin spec → plan → implement → refine → light verify → optional hardening.
- Do not weaken deterministic guardrails.
- Do not convert behavior contracts into implementation leakage.
- Specs describe external observables only.
- Human approval is required for charter and architecture decisions.
- Acceptance tests and unit tests are separate streams; both must pass.
- Mutation testing verifies test quality when required by the workflow/charter.
- Generated tests are regenerated from specs; they are not hand-edited.
- Handoffs are durable gates, not chat summaries.
- Verification independence matters: verifier/architect must not be the implementer/refiner for the same phase.
- New-project prompts must enter DAE project-start intake; do not scaffold or write source/config/test files until charter, ACs, Gherkin spec, plan, and non-stale human plan approval exist.

## Codex release rules

- Keep Codex-native plugin, skill, hook, and custom agent surfaces as the primary release path.
- Use `.agents/plugins/marketplace.json` for repo marketplace metadata.
- Use `.codex-plugin/plugin.json` for plugin manifests.
- Use `.codex/agents/*.toml` for project-scoped custom agents unless plugin-bundled agents are verified.
- Use `PLUGIN_ROOT` and `PLUGIN_DATA` as primary hook/script variables; legacy compatibility variables may remain only as tested fallback.
- Do not enable unsafe permissions by default.
- Keep local evidence harnesses such as `.dae-verification/` and `.dae-production-readiness/` out of release packaging.
- Keep `.dae-project-start-enforcement/` as local probe evidence only; the release path is the plugin code, contracts, hooks, installer, and docs.

## Validation

Before claiming completion, run relevant tests and:

```bash
python3 codex-migration-task/validators/validate_codex_migration.py .
python3 -m unittest discover plugins/engineer/scripts
```

Document failed or unavailable commands with evidence.
