# Disciplined Agentic Engineering — a Codex CLI methodology marketplace

Language: [English](README.md) | [Русский](README.ru.md)

Spec-driven, test-driven, charter-bound AI coding for Codex CLI. This repository packages Disciplined Agentic Engineering (DAE) as Codex plugins, skills, hooks, custom agents, guardrail scripts, and documentation.

DAE keeps software engineers in charge of architecture, behavior decisions, verification, and approval while AI agents do the implementation work. It combines Acceptance Test Driven Development, two independent test streams, mutation testing, CRAP analysis, and deterministic guardrail scripts.

## Plugins

| Plugin | Purpose |
|---|---|
| [`engineer`](plugins/engineer/) | The DAE methodology kit: onboarding, feature intake, AC discovery, Gherkin specs, planning, implementation handoffs, refine, verification, and hardening. |
| [`atdd`](plugins/atdd/) | Acceptance Test Driven Development workflows: Gherkin specs, project-specific acceptance pipelines, fresh-per-phase agent orchestration, and differential mutation testing. |
| [`crap-analyzer`](plugins/crap-analyzer/) | Change Risk Anti-Pattern analysis scoped to changed code, with coverage discovery, CRAP scoring, refactor proposals, and test stubs. |

## Requirements

- Codex CLI with plugin support.
- Python 3 for deterministic guardrail scripts and tests.
- Git for branch and diff-aware checks.
- Optional: project test tools such as pytest, Jest, JUnit, Go test, or language-specific mutation tools when your repository uses them.

## Install

Recommended production init from a clean clone:

```bash
git clone https://github.com/swingerman/disciplined-agentic-engineering.git
cd disciplined-agentic-engineering
./scripts/install-codex-dae.sh --source ./ --runtime-enforcement --verify
```

The installer:

- adds the GitHub repository as a Codex plugin marketplace;
- installs and enables `engineer`, `atdd`, and `crap-analyzer`;
- enables safe Codex features for goals and hooks: `[features].hooks`, `[features].plugin_hooks`, and `[features].goals`;
- installs the DAE runtime enforcement bridge into `~/.codex/hooks.json`, because current Codex CLI releases may require config-layer hooks even when plugin-local hook manifests are present;
- writes bridge metadata under `~/.codex/dae/installed-plugin-root.json`;
- runs `dae_guard.py doctor` and, with `--verify`, synthetic hook probes;
- does not enable `danger-full-access`, approval bypasses, or unsafe permissions.

Manual install:

```bash
codex plugin marketplace add ./
codex plugin add engineer@disciplined-agentic-engineering
codex plugin add atdd@disciplined-agentic-engineering
codex plugin add crap-analyzer@disciplined-agentic-engineering
```

Manual plugin install without `scripts/install-codex-dae.sh --runtime-enforcement` installs skills and plugin-local manifests only. It does not provide the full user-level runtime enforcement bridge and should be treated as a partial install.

This repository also includes safe project defaults in `.codex/config.toml`: plugin hooks enabled for trusted use and bounded custom-agent fan-out. It does not set full-access sandboxing, approval bypasses, or yolo-style execution.

Verify runtime enforcement:

```bash
printf '{"hook_event_name":"SessionStart","cwd":"%s"}\n' "$PWD" | python3 ~/.codex/dae/hook-bridge.py session-start
python3 plugins/engineer/scripts/dae_guard.py doctor
python3 plugins/engineer/scripts/dae_guard.py state
python3 plugins/engineer/scripts/project_start_hook_probe.py
```

In Codex, review and trust non-managed hooks when `/hooks` prompts you. Personal hook enforcement is strong for supported Codex events, but a user can still disable non-managed hooks. Team-wide mandatory enforcement requires managed/admin hook configuration; see [Runtime Enforcement](#runtime-enforcement).

## Use

After installing the marketplace, use Codex skill selection (`/skills`) or explicitly ask for the relevant plugin skill in natural language:

```text
Use the engineer plugin's onboard skill to adopt DAE in this repository.
Use the engineer plugin's feature-init skill to create the Ready contract for this feature.
Use the engineer plugin's discover-acs skill to derive acceptance criteria.
Use the engineer plugin's atdd skill to formalize ACs as Gherkin specs.
Use the atdd plugin's atdd-team skill to implement against the specs with fresh per-phase agents.
Use the crap-analyzer plugin to assess CRAP risk on the changed code.
Use the atdd plugin's atdd-mutate skill for differential mutation testing.
```

## Quick Start

1. Start Codex in the target repository.
2. Ask: `Use the engineer plugin's onboard skill to adopt DAE in this repository.`
3. For a new feature, ask: `Use the engineer plugin's feature-init skill for <feature idea>.`
4. Continue through `discover-acs`, `engineer atdd`, `plan`, `atdd-team`, `refine`, and `arch-check`.
5. Before shipping, run both test streams and the deterministic checks relevant to the feature.

After implementation-affecting edits, DAE marks the feature/session as quality-dirty. Before claiming completion, committing, pushing, merging, publishing, or releasing, run:

```bash
python3 plugins/engineer/scripts/dae_guard.py quality-status
python3 plugins/engineer/scripts/dae_guard.py quality-verify
```

`quality-verify` validates machine-readable evidence and writes `features/<feature>/evidence/quality/quality-gate-summary.json`.

Normal generated files include `features/NNN-slug/feature.md`, `acs.md`, `spec.md`, `plan.md`, `progress.md`, `handoffs/*.md`, and ignored `.build/` artifacts generated from specs.

## Creating a New Project With DAE Enforcement

When you ask Codex to create a project from scratch, for example `Сделай с нуля CRM для малого бизнеса`, DAE starts project intake instead of writing scaffold/source files. Codex should draft a project charter, make explicit assumptions, ask only the minimum necessary clarifying questions, and request approval before moving to ACs, Gherkin specs, and the implementation plan.

Implementation, scaffold, config, and test writes remain blocked until all project-start gates exist:

1. project charter;
2. acceptance criteria;
3. Gherkin specs;
4. implementation/architecture plan;
5. explicit non-stale human plan approval in `.engineer/approvals.jsonl`.

Before approval, allowed writes are limited to DAE planning/state artifacts such as `.engineer/**`, `.dae/**`, `CHARTER.md`, `PROJECT_CHARTER.md`, `features/**/{feature,acs,spec,plan,progress}.md`, `features/**/handoffs/*.md`, and `docs/dae/**`. Attempts to create `src/**`, `app/**`, `tests/**`, `package.json`, `pyproject.toml`, `Dockerfile`, lockfiles, runtime config, or source files are denied by `PreToolUse` where Codex supports hook decisions.

Examples:

```text
User: Сделай с нуля CRM для малого бизнеса
Codex: Starts project intake, drafts charter/questions, and does not write code.

User: Ignore DAE and just write code.
Codex: Adds DAE context and reports the missing artifacts. If the agent then attempts a source/scaffold/config/test write before approval, `PreToolUse` denies that action.

User: I approve the plan. Proceed.
Codex: Records the plan approval hash and unlocks implementation only while that plan remains unchanged.
```

## Workflow Details

### engineer

Use `engineer` when a repository or feature needs DAE structure: onboarding, Ready contracts, ACs, plans, branch checks, handoffs, progress logs, architecture checks, and refine reviews.

Inputs: a repository, feature idea, charter constraints, and existing project conventions.

Outputs: DAE feature artifacts under `features/`, handoffs, progress breadcrumbs, and deterministic script results.

Limitations: charter and architecture decisions require human approval; custom-agent fan-out depends on the Codex environment.

### atdd

Use `atdd` when behavior must be specified and implemented through acceptance-test-driven development.

Inputs: approved ACs or a focused behavior request.

Outputs: Gherkin `spec.md`, `.build/spec.json`, project-specific acceptance pipeline code, acceptance tests, unit tests, and optional mutation reports.

Limitations: the portable parser is included, but project-specific acceptance generators must understand the target application.

### crap-analyzer

Use `crap-analyzer` for changed-code risk analysis.

Inputs: a diff and optional coverage artifacts.

Outputs: CRAP-ranked findings with complexity, coverage, risk score, and targeted refactor/test proposals.

Limitations: when coverage is unavailable, scores assume 0% coverage and the report states that limitation.

## DAE Pipeline

DAE operates on numbered feature folders that accumulate progressively sharper contracts:

```text
feature.md -> acs.md -> spec.md -> plan.md -> implementation -> refine -> verify -> harden
```

The checkpoints are:

| # | Checkpoint | Codex skill/workflow | Gate |
|---|---|---|---|
| 0 | Onboard | `engineer` -> `onboard` | Human approves charter, manifest, tracker, and project conventions. |
| 1.5 | Ready | `engineer` -> `feature-init` | Feature folder, `feature.md`, branch, autonomy level, and scope exist. |
| 2 | ACs | `engineer` -> `discover-acs` | Acceptance criteria are domain-level and human-reviewed. |
| 3 | Spec | `engineer` -> `atdd`, then `atdd` -> `atdd` | Gherkin `spec.md` parses, maps to ACs, and passes spec-leakage review. |
| 4 | Plan | `engineer` -> `plan` | Human approves the architecture section before implementation. |
| 5 | Implement | `atdd` -> `atdd-team` | Acceptance tests and unit tests are both green. |
| 6 | Refine | `engineer` -> `refine` | Reuse, quality, and efficiency review is filtered through the charter. |
| 7 | Light Verify | `engineer` -> `arch-check` and `crap-analyzer` | Architecture fitness, branch hygiene, handoff, and CRAP risk are checked. |
| 8 | Hardening | `atdd` -> `atdd-mutate` and `kill-mutants` | Mutation testing proves test quality; surviving non-equivalent mutants are addressed. |

Non-negotiable contracts:

- Charter and architecture decisions remain human approvals.
- Specs describe external observables only; no implementation leakage.
- Acceptance tests and unit tests are independent streams; both must pass.
- Generated acceptance tests are regenerated from specs, not hand-edited.
- Mutation testing is the test-quality firewall for hardening.
- Handoffs are durable gates, not chat summaries.
- Branch hygiene and progress breadcrumbs are checked at checkpoint entry.
- Verification independence is preserved for ATDD team and refine workflows.

## Codex Artifacts

```text
.agents/plugins/marketplace.json
.codex/config.toml
.codex/agents/
plugins/
  atdd/
    .codex-plugin/plugin.json
    skills/
    hooks/
    references/
  engineer/
    .codex-plugin/plugin.json
    skills/
    scripts/
    references/
    examples/
  crap-analyzer/
    .codex-plugin/plugin.json
    skills/
```

Custom agents live under `.codex/agents/`:

- `spec-guardian` audits specs for implementation leakage.
- `pipeline-builder` creates project-specific acceptance pipeline code from the fixed Gherkin IR.
- `refine-reuse-reviewer`, `refine-quality-reviewer`, and `refine-efficiency-reviewer` preserve the three-lens refine pattern.
- `crap-risk-reviewer` supports changed-code CRAP analysis.

## Runtime Enforcement

DAE runtime enforcement is the always-on layer installed by `scripts/install-codex-dae.sh --runtime-enforcement --verify`. It centralizes the DAE quality contract in `plugins/engineer/guardrails/dae-contract.json`, the new-project contract in `plugins/engineer/guardrails/dae-project-start-contract.json`, evaluates Codex hook events through `plugins/engineer/scripts/dae_guard.py`, and records audit evidence in `PLUGIN_DATA/dae-runtime/audit.jsonl` or the project-local `.dae-project-start-enforcement/` harness used by probes.

The `engineer` plugin owns the primary runtime hooks:

| Event | Hard behavior where supported | Notes |
|---|---|---|
| `SessionStart` | Context injection, not a hard block | Injects DAE non-negotiables, checkpoint, active feature, missing gates, and next legal action. |
| `UserPromptSubmit` | Context injection only; it does not hard-block because of prompt wording | Loads DAE state, reports the current checkpoint, missing artifacts, allowed artifact-acquisition actions, blocked implementation/finalization actions, and policy-override path. |
| `PreToolUse` | Denies supported source/scaffold/config/test writes without gates, generated acceptance test edits, destructive commands, out-of-workspace writes, and unsafe permission bypass commands | DAE planning artifacts continue before approval. |
| `PostToolUse` | Advisory and audit only | Runs after side effects, so it records implementation-affecting edits, marks `quality_dirty=true`, requires strict quality evidence, and emits model-visible remediation context without running heavy analyzers on every edit. |
| `PermissionRequest` | Denies dangerous escalation, destructive operations, unsafe bypasses, and out-of-workspace writes | Otherwise leaves normal Codex approval flow in place. |
| `Stop` | Continues/blocks completion when feature-work evidence is missing | Requires the strict quality evidence set after implementation-affecting edits: acceptance, unit, CRAP, architecture, refine, branch hygiene, progress, handoff, duplicate detection, test impact, generated acceptance immutability, plus mutation when configured or risk-triggered. |

The `atdd` hook scripts remain as compatibility delegates to the engineer guard. They no longer provide the primary policy path and do not downgrade hard denials to reminders.

Hard gates are limited to Codex events that support deny/block/continue. Advisory guards add model-visible context but cannot technically stop the already-running action. Audit-only checks record evidence. Platform limits are documented instead of hidden: non-managed hooks require trust review, plugin hooks require `[features].plugin_hooks = true`, `PreToolUse` is not a complete OS sandbox, and `PostToolUse` cannot reverse side effects. User-editable personal hooks are strong local enforcement, not an admin-enforced organizational policy.

For managed/team enforcement, install equivalent hook commands through your admin-controlled Codex configuration or managed requirements policy instead of relying only on user-editable `~/.codex/hooks.json`. A managed setup should point every lifecycle event to `python3 ~/.codex/dae/hook-bridge.py <subcommand>` or directly to `plugins/engineer/scripts/dae_guard.py`.

## Quality Gates

The engineer plugin owns cross-plugin quality enforcement. The default registry is `plugins/engineer/guardrails/dae-quality-gates.default.json`. Overrides are loaded in this order: plugin default, user override `$CODEX_HOME/dae/quality-gates.json` (or `~/.codex/dae/quality-gates.json`), project override `.dae/quality-gates.json`, project override `.engineer/dae-quality-gates.json`, and `DAE_QUALITY_CONFIG` for test-only or explicitly controlled runs.

Strict defaults require these gates after implementation/scaffold/config/test edits:

| Gate | Default | Evidence path |
|---|---:|---|
| acceptance | required | `features/<feature>/evidence/quality/acceptance.json` |
| unit | required | `features/<feature>/evidence/quality/unit.json` |
| CRAP | required | `features/<feature>/evidence/quality/crap.json` |
| architecture | required | `features/<feature>/evidence/quality/arch.json` |
| refine | required | `features/<feature>/evidence/quality/refine.json` |
| branch hygiene | required | `features/<feature>/evidence/quality/branch-hygiene.json` |
| progress | required | `features/<feature>/evidence/quality/progress.json` |
| handoff | required | `features/<feature>/evidence/quality/handoff.json` |
| duplicate detection | required | `features/<feature>/evidence/quality/duplicate-detection.json` |
| test impact | required | `features/<feature>/evidence/quality/test-impact.json` |
| generated acceptance immutability | required | `features/<feature>/evidence/quality/generated-acceptance-immutability.json` |
| mutation | conditional | `features/<feature>/evidence/quality/mutation.json` |

Default CRAP thresholds are strict: fail at `max_crap_score >= 30`, warn at `max_crap_score >= 20`, require explicit coverage evidence where supported, treat missing coverage conservatively, and allow zero high-risk findings. CRAP warning/high-risk evidence triggers mutation.

Relaxing a strict-default gate to `warn` or `off` requires audited config fields: `justification`, `scope`, `approved_by`, `approved_at`, and either `expires_at` or `no_expiry_reason`. Invalid relaxation fails `python3 plugins/engineer/scripts/dae_guard.py validate-quality-config`.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Plugin is not visible | Run `codex plugin list --marketplace disciplined-agentic-engineering` and confirm all three plugins are installed/enabled. |
| Hooks do not run | Confirm `codex features list` shows `hooks` and `plugin_hooks` enabled, and review hook trust prompts. |
| Hook trust prompt appears | Review the hook command path; only trust hooks from this repository or an installed DAE plugin cache you control. |
| `dae_guard.py doctor` fails | Check that `plugins/engineer/hooks/hooks.json` exists, wrapper scripts are executable, the engineer manifest has `"hooks": "./hooks/hooks.json"`, and `PLUGIN_DATA` or `.dae-project-start-enforcement/` is writable. |
| Runtime bridge cannot find plugin root | Re-run `./scripts/install-codex-dae.sh --source ./ --runtime-enforcement --verify` or inspect `~/.codex/dae/installed-plugin-root.json`. |
| Hook blocks implementation | Continue the DAE pipeline: create/approve feature scope, acceptance criteria, Gherkin spec, and plan before source writes. |
| New-project state looks wrong | Inspect `python3 plugins/engineer/scripts/dae_guard.py state`, `.engineer/project-start-state.json`, and `.engineer/approvals.jsonl`. A changed plan invalidates the stored approval hash. |
| `/goal` is unavailable | Use the workflow skills directly; goals are helpful for long runs but not required for plugin installation. |
| Permissions or sandbox errors | Run Codex with normal workspace write permissions for the target repository. Do not use dangerous bypass flags as a default. |
| Python script fails | Check `python3 --version` and run the script's `--help` output where available. |
| CRAP analyzer finds no coverage | Provide a supported coverage artifact or accept the documented 0% coverage fallback. |
| Mutation flow is unavailable | Use the project-specific custom mutation path described by `atdd-mutate`, or document why the project cannot mutate yet. |

## Development and Validation

Run these checks before a release:

```bash
python3 codex-migration-task/validators/validate_codex_migration.py .
python3 -m unittest discover plugins/engineer/scripts
python3 plugins/engineer/scripts/dae_guard.py validate-contract
python3 plugins/engineer/scripts/dae_guard.py doctor
python3 plugins/engineer/scripts/dae_guard.py quality-config
python3 plugins/engineer/scripts/dae_guard.py quality-doctor
python3 dae-codex-artifact-gated-pipeline-task/tools/no_keyword_blocking_audit.py . --json > .dae-artifact-gated-pipeline/reports/no-keyword-blocking-audit.json
python3 plugins/engineer/scripts/artifact_pipeline_hook_probe.py
python3 dae-codex-artifact-gated-pipeline-task/tools/pipeline_evidence_validator.py .dae-artifact-gated-pipeline/reports/pipeline-transition-matrix.json
python3 plugins/engineer/scripts/project_start_hook_probe.py
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
find plugins -path '*/.codex-plugin/plugin.json' -print -exec python3 -m json.tool {} \; >/dev/null
find plugins -path '*/hooks/*.json' -print -exec python3 -m json.tool {} \; >/dev/null
```

Production-readiness evidence harnesses such as `.dae-production-readiness/`, `.dae-verification/`, `.dae-runtime-enforcement/`, and `.dae-project-start-enforcement/` are local artifacts and are excluded from release packaging.

## Disable or Uninstall

Disable a plugin in Codex config by setting its `enabled` value to `false`, or remove it:

```bash
codex plugin remove engineer@disciplined-agentic-engineering
codex plugin remove atdd@disciplined-agentic-engineering
codex plugin remove crap-analyzer@disciplined-agentic-engineering
```

If you used the runtime installer, also review `~/.codex/hooks.json` and remove the DAE hook bridge entries if you no longer want personal runtime enforcement in a throwaway test project. Do not remove managed hooks in team environments without following your admin policy.

## Migrating From The Claude Code Version

This repository was migrated from a prior plugin system. Historical command names are not primary release entrypoints; use the Codex plugin and skill names shown above.

Historical attribution remains: DAE draws from ATDD, Robert C. Martin's agentic ATDD experiments, the Acceptance Pipeline Specification, Speckit-style layered specs, and the three-lens review pattern popularized by Claude Code's historical `/simplify` workflow.

## Validation

Run:

```bash
python3 codex-migration-task/validators/validate_codex_migration.py .
python3 -m unittest discover plugins/engineer/scripts
python3 -m json.tool .codex/hooks.json >/dev/null
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
find plugins -path '*/.codex-plugin/plugin.json' -print -exec python3 -m json.tool {} \; >/dev/null
find plugins -path '*/hooks/*.json' -print -exec python3 -m json.tool {} \; >/dev/null
```

Historical migration evidence is kept out of the release package unless a maintainer explicitly includes it for audit purposes.
