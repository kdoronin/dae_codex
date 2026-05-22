# Engineer Codex Plugin

Disciplined Agentic Engineering methodology kit for Codex CLI.

The plugin implements the DAE checkpoints and ships the deterministic scripts that enforce handoffs, branch hygiene, progress breadcrumbs, architecture checks, duplicate detection, Gherkin parsing, impact analysis, and mutation-map selection.

It also owns the DAE runtime enforcement layer for Codex hooks. Runtime enforcement is initialized by the repository installer, uses `guardrails/dae-contract.json` plus `guardrails/dae-project-start-contract.json` as machine-readable contract registries, and routes all hook events through `scripts/dae_guard.py`.

## Skills

| Skill | Checkpoint | Purpose |
|---|---:|---|
| `onboard` | 0 | Create charter, manifest, tracker, and project conventions. |
| `discuss` | - | Explore, park, or promote feature ideas. |
| `feature-init` | 1.5 | Create a feature folder, Ready contract, branch, and autonomy level. |
| `prime-context` | - | Load context for a Ready feature before AC discovery. |
| `discover-acs` | 2 | Derive acceptance criteria in domain language. |
| `atdd` | 3 | Bridge to the ATDD plugin for Gherkin specs and acceptance pipeline generation. |
| `plan` | 4 | Produce an architecture plan and structured charter check for human approval. |
| `refine` | 6 | Run reuse, quality, and efficiency review through the charter filter. |
| `arch-check` | 7 | Run architecture fitness checks from manifest rules. |
| `clarify` | - | Resolve ambiguity in one DAE artifact. |
| `consistency-check` | - | Validate cross-artifact consistency read-only. |
| `feature-edit` | - | Propagate intentional feature changes across downstream artifacts. |
| `progress-log` | - | Convert handoffs into `progress.md` and tracker updates. |
| `reorient` | - | Re-anchor after compaction or long-running work. |
| `session-summary` | - | Append a human-readable session log. |
| `next` | - | Survey DAE state and recommend the next task. |

## Guardrail Scripts

Scripts live in `scripts/` and are stdlib-only Python unless noted:

- `dae_resolve.py` resolves methodology root and manifest.
- `dae_handoff.py` enforces handoff-as-gate.
- `dae_branch.py` enforces feature branch hygiene.
- `dae_progress.py` renders the pipeline breadcrumb.
- `dae_arch.py` checks layering, cycles, forbidden patterns, naming, and file size.
- `dae_dup.py` feeds duplicate findings into refine.
- `dae_gherkin.py` and related tools parse and mutate Gherkin IR.
- `dae_impact.py` supports acceptance test impact selection.
- `dae_mutmap.py` supports differential mutation selection.
- `dae_tracker_local.py` implements the local tracker driver.
- `dae_guard.py` evaluates Codex lifecycle hook events, checks DAE state and approvals, emits deny/block/continue/context responses, and writes runtime audit JSONL.
- `project_start_hook_probe.py` runs synthetic hook probes and fixture repos for new-project enforcement, writing `.dae-project-start-enforcement/reports/project-start-enforcement-matrix.json`.

## Runtime Hooks

`hooks/hooks.json` wires the guard to all supported lifecycle events:

- `SessionStart` injects DAE context and current checkpoint state.
- `UserPromptSubmit` routes normal new-project prompts such as `Сделай с нуля CRM для малого бизнеса` into project-start intake and blocks explicit DAE bypass or guardrail-disable prompts.
- `PreToolUse` denies supported source/scaffold/config/test writes before charter, ACs, Gherkin spec, plan, and non-stale human plan approval exist; DAE planning artifacts remain allowed before approval.
- `PostToolUse` records source edits and emits advisory remediation context because the tool has already run.
- `PermissionRequest` denies dangerous or DAE-bypassing escalations.
- `Stop` continues the turn when feature-work completion evidence is missing.

The hard/advisory split is intentional. User-installed non-managed hooks require Codex trust and can be disabled by the user; mandatory organization-wide enforcement must be installed as managed hooks by an administrator.

## New Project Intake

Project-start state is stored in `.engineer/project-start-state.json`; human plan approval is stored as a hash-checked JSONL event in `.engineer/approvals.jsonl`. Before approval, Codex may write only planning/state artifacts such as `.engineer/**`, `.dae/**`, `CHARTER.md`, `features/**/{feature,acs,spec,plan,progress}.md`, `features/**/handoffs/*.md`, and `docs/dae/**`.

Scaffold and implementation targets such as `src/**`, `app/**`, `tests/**`, `package.json`, `pyproject.toml`, `Dockerfile`, lockfiles, and language source files are blocked before the approved plan hash matches the current plan.

## Custom Agents

Project-scoped Codex custom agents live in `.codex/agents/`. The engineer workflow uses `spec-guardian`, `pipeline-builder`, and the three refine reviewer agents when available. If a Codex environment cannot load custom agents, the skills include the same role contracts as fallback instructions.

## Methodology Rules

Charter approval and architecture approval remain human decisions. Handoffs are gates. Branch hygiene and progress breadcrumbs are checked at checkpoint entry. Acceptance and unit streams are separate. Specs stay domain-level. Mutation testing verifies test quality during hardening.

## Inputs, Outputs, and Limits

Inputs are the target repository, feature idea, charter constraints, and existing project conventions. Outputs are feature folders, ACs, specs, plans, handoffs, progress logs, and deterministic script evidence. The plugin guides and gates the DAE process; it does not remove the need for human approval on charter or architecture decisions.
