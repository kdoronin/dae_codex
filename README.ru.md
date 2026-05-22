# Disciplined Agentic Engineering — marketplace методологии для Codex CLI

Язык: [English](README.md) | [Русский](README.ru.md)

Spec-driven, test-driven и charter-bound разработка с AI-агентами для Codex CLI. Этот репозиторий упаковывает Disciplined Agentic Engineering (DAE) как плагины Codex, skills, hooks, custom agents, guardrail-скрипты и документацию.

DAE оставляет архитектуру, поведенческие решения, проверку и approvals за инженером, а AI-агенты выполняют реализацию. Методология объединяет Acceptance Test Driven Development, два независимых тестовых потока, mutation testing, CRAP-анализ и детерминированные guardrail-скрипты.

## Плагины

| Плагин | Назначение |
|---|---|
| [`engineer`](plugins/engineer/) | Методологический набор DAE: onboarding, intake фичи, discovery acceptance criteria, Gherkin specs, planning, implementation handoffs, refine, verification и hardening. |
| [`atdd`](plugins/atdd/) | Acceptance Test Driven Development workflow: Gherkin specs, проектные acceptance pipelines, fresh-per-phase agent orchestration и differential mutation testing. |
| [`crap-analyzer`](plugins/crap-analyzer/) | Change Risk Anti-Pattern анализ измененного кода: discovery покрытия, CRAP scoring, предложения по refactor и test stubs. |

## Требования

- Codex CLI с поддержкой plugins.
- Python 3 для детерминированных guardrail-скриптов и тестов.
- Git для branch- и diff-aware проверок.
- Опционально: проектные test tools, например pytest, Jest, JUnit, Go test или language-specific mutation tools, если они используются в вашем репозитории.

## Установка

Рекомендуемая локальная установка из чистого clone:

```bash
git clone https://github.com/swingerman/disciplined-agentic-engineering.git
cd disciplined-agentic-engineering
./scripts/install-codex-dae.sh --source ./
```

Installer:

- добавляет GitHub-репозиторий как Codex plugin marketplace;
- устанавливает и включает `engineer`, `atdd` и `crap-analyzer`;
- включает безопасные Codex features для goals и hooks;
- устанавливает DAE runtime hook bridge в `~/.codex/hooks.json`, потому что текущие Codex CLI releases могут требовать config-layer hooks даже при наличии plugin-local hook manifests;
- не включает `danger-full-access`, approval bypasses или небезопасные permissions.

Ручная установка:

```bash
codex plugin marketplace add ./
codex plugin add engineer@disciplined-agentic-engineering
codex plugin add atdd@disciplined-agentic-engineering
codex plugin add crap-analyzer@disciplined-agentic-engineering
```

В репозитории также есть безопасные проектные defaults в `.codex/config.toml`: plugin hooks включены для trusted use, custom-agent fan-out ограничен. Конфигурация не включает full-access sandboxing, approval bypasses или yolo-style execution.

## Использование

После установки marketplace используйте выбор Codex skills (`/skills`) или явно попросите нужный plugin skill естественным языком:

```text
Use the engineer plugin's onboard skill to adopt DAE in this repository.
Use the engineer plugin's feature-init skill to create the Ready contract for this feature.
Use the engineer plugin's discover-acs skill to derive acceptance criteria.
Use the engineer plugin's atdd skill to formalize ACs as Gherkin specs.
Use the atdd plugin's atdd-team skill to implement against the specs with fresh per-phase agents.
Use the crap-analyzer plugin to assess CRAP risk on the changed code.
Use the atdd plugin's atdd-mutate skill for differential mutation testing.
```

## Быстрый старт

1. Запустите Codex в целевом репозитории.
2. Попросите: `Use the engineer plugin's onboard skill to adopt DAE in this repository.`
3. Для новой фичи попросите: `Use the engineer plugin's feature-init skill for <feature idea>.`
4. Пройдите через `discover-acs`, `engineer atdd`, `plan`, `atdd-team`, `refine` и `arch-check`.
5. Перед поставкой запустите оба тестовых потока и детерминированные проверки, релевантные фиче.

Обычные generated files: `features/NNN-slug/feature.md`, `acs.md`, `spec.md`, `plan.md`, `progress.md`, `handoffs/*.md` и ignored `.build/` artifacts, сгенерированные из specs.

## Подробности workflow

### engineer

Используйте `engineer`, когда репозиторию или фиче нужна структура DAE: onboarding, Ready contracts, ACs, plans, branch checks, handoffs, progress logs, architecture checks и refine reviews.

Inputs: репозиторий, идея фичи, charter constraints и существующие conventions проекта.

Outputs: DAE feature artifacts в `features/`, handoffs, progress breadcrumbs и результаты deterministic scripts.

Ограничения: charter и architecture decisions требуют human approval; custom-agent fan-out зависит от Codex environment.

### atdd

Используйте `atdd`, когда поведение должно быть описано и реализовано через acceptance-test-driven development.

Inputs: approved ACs или focused behavior request.

Outputs: Gherkin `spec.md`, `.build/spec.json`, project-specific acceptance pipeline code, acceptance tests, unit tests и optional mutation reports.

Ограничения: portable parser включен, но project-specific acceptance generators должны понимать целевое приложение.

### crap-analyzer

Используйте `crap-analyzer` для risk analysis измененного кода.

Inputs: diff и optional coverage artifacts.

Outputs: CRAP-ranked findings с complexity, coverage, risk score и targeted refactor/test proposals.

Ограничения: если coverage недоступно, score рассчитывается с предположением 0% coverage, и report явно указывает это ограничение.

## DAE Pipeline

DAE работает с numbered feature folders, которые постепенно накапливают более точные contracts:

```text
feature.md -> acs.md -> spec.md -> plan.md -> implementation -> refine -> verify -> harden
```

Checkpoints:

| # | Checkpoint | Codex skill/workflow | Gate |
|---|---|---|---|
| 0 | Onboard | `engineer` -> `onboard` | Человек approve-ит charter, manifest, tracker и project conventions. |
| 1.5 | Ready | `engineer` -> `feature-init` | Feature folder, `feature.md`, branch, autonomy level и scope существуют. |
| 2 | ACs | `engineer` -> `discover-acs` | Acceptance criteria domain-level и human-reviewed. |
| 3 | Spec | `engineer` -> `atdd`, затем `atdd` -> `atdd` | Gherkin `spec.md` parses, maps to ACs и проходит spec-leakage review. |
| 4 | Plan | `engineer` -> `plan` | Человек approve-ит architecture section до implementation. |
| 5 | Implement | `atdd` -> `atdd-team` | Acceptance tests и unit tests оба green. |
| 6 | Refine | `engineer` -> `refine` | Reuse, quality и efficiency review проходят через charter. |
| 7 | Light Verify | `engineer` -> `arch-check` и `crap-analyzer` | Проверяются architecture fitness, branch hygiene, handoff и CRAP risk. |
| 8 | Hardening | `atdd` -> `atdd-mutate` и `kill-mutants` | Mutation testing доказывает test quality; surviving non-equivalent mutants обрабатываются. |

Непересматриваемые contracts:

- Charter и architecture decisions остаются human approvals.
- Specs описывают только external observables; implementation leakage запрещен.
- Acceptance tests и unit tests являются независимыми streams; оба должны pass.
- Generated acceptance tests регенерируются из specs, а не редактируются вручную.
- Mutation testing является test-quality firewall для hardening.
- Handoffs являются durable gates, а не chat summaries.
- Branch hygiene и progress breadcrumbs проверяются на входе в checkpoint.
- Verification independence сохраняется для ATDD team и refine workflows.

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

Custom agents находятся в `.codex/agents/`:

- `spec-guardian` проверяет specs на implementation leakage.
- `pipeline-builder` создает project-specific acceptance pipeline code из fixed Gherkin IR.
- `refine-reuse-reviewer`, `refine-quality-reviewer` и `refine-efficiency-reviewer` сохраняют three-lens refine pattern.
- `crap-risk-reviewer` поддерживает changed-code CRAP analysis.

## Runtime Enforcement

Основной runtime-слой принадлежит плагину `engineer`: `plugins/engineer/hooks/hooks.json` подключает `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PermissionRequest` и `Stop` к `plugins/engineer/scripts/dae_guard.py`. Installer `scripts/install-codex-dae.sh --runtime-enforcement --verify` дополнительно ставит user-level bridge в `~/.codex/hooks.json`.

`UserPromptSubmit` только добавляет контекст: текущий checkpoint, missing artifacts, допустимые artifact-acquisition actions, запрещенные implementation/finalization actions и путь через `.engineer/policy-overrides.jsonl` для policy changes. Он не hard-block-ит prompt из-за слов в тексте.

`PostToolUse` после implementation/scaffold/config/test edits не запускает дорогие анализаторы на каждое изменение. Он помечает `.engineer/quality-state.json` как `quality_dirty=true`, вычисляет обязательные evidence gates и показывает следующий допустимый шаг: `quality-verify`.

`PreToolUse` блокирует поддерживаемые release/finalization actions, включая `git commit`, `git push`, merge, publish и deploy, пока quality dirty или evidence failing. `Stop` не дает завершить работу без machine-readable evidence.

## Quality Gates

Strict default policy лежит в `plugins/engineer/guardrails/dae-quality-gates.default.json`. Overrides читаются из user config `$CODEX_HOME/dae/quality-gates.json` или `~/.codex/dae/quality-gates.json`, project config `.dae/quality-gates.json`, `.engineer/dae-quality-gates.json` и `DAE_QUALITY_CONFIG`.

После implementation-affecting changes по умолчанию обязательны: acceptance stream, unit stream, CRAP, architecture, refine, branch hygiene, progress, handoff, duplicate detection, test impact, generated acceptance immutability; mutation обязательна при hardening/config или CRAP/risk trigger.

Evidence пишется в:

```text
features/<feature>/evidence/quality/<gate>.json
features/<feature>/evidence/quality/quality-gate-summary.json
```

CRAP обязателен по умолчанию. Strict thresholds: fail при `max_crap_score >= 30`, warn при `max_crap_score >= 20`, missing coverage не проходит молча, high-risk findings должны быть `0`. Relax strict gates to `warn` или `off` можно только с audited fields: `justification`, `scope`, `approved_by`, `approved_at` и `expires_at` либо `no_expiry_reason`.

## Troubleshooting

| Симптом | Что проверить |
|---|---|
| Plugin не виден | Запустите `codex plugin list --marketplace disciplined-agentic-engineering` и убедитесь, что все три plugins установлены и enabled. |
| Hooks не запускаются | Убедитесь, что `codex features list` показывает `hooks` и `plugin_hooks` enabled, и проверьте hook trust prompts. |
| Появляется hook trust prompt | Проверьте hook command path; доверяйте только hooks из этого репозитория или установленного DAE plugin cache, который вы контролируете. |
| `/goal` недоступен | Используйте workflow skills напрямую; goals полезны для длинных runs, но не обязательны для plugin installation. |
| Permissions или sandbox errors | Запускайте Codex с обычными workspace write permissions для целевого репозитория. Не используйте dangerous bypass flags по умолчанию. |
| Python script падает | Проверьте `python3 --version` и запустите `--help` для script, если он доступен. |
| CRAP analyzer не находит coverage | Передайте supported coverage artifact или примите documented 0% coverage fallback. |
| Mutation flow недоступен | Используйте project-specific custom mutation path, описанный `atdd-mutate`, или задокументируйте, почему project пока не может выполнять mutation. |

## Development and Validation

Запускайте эти проверки перед release:

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
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
find plugins -path '*/.codex-plugin/plugin.json' -print -exec python3 -m json.tool {} \; >/dev/null
find plugins -path '*/hooks/*.json' -print -exec python3 -m json.tool {} \; >/dev/null
```

Production-readiness evidence harnesses, например `.dae-production-readiness/` и `.dae-verification/`, являются local artifacts и исключены из release packaging.

## Disable or Uninstall

Отключите plugin в Codex config, установив `enabled` в `false`, или удалите его:

```bash
codex plugin remove engineer@disciplined-agentic-engineering
codex plugin remove atdd@disciplined-agentic-engineering
codex plugin remove crap-analyzer@disciplined-agentic-engineering
```

Если вы использовали installer, также проверьте `~/.codex/hooks.json` и удалите DAE hook bridge entries, если advisory ATDD hooks больше не нужны.

## Migrating From The Claude Code Version

Этот репозиторий был мигрирован из предыдущей plugin system. Исторические command names не являются primary release entrypoints; используйте Codex plugin и skill names, указанные выше.

Historical attribution сохраняется: DAE опирается на ATDD, agentic ATDD experiments Роберта Мартина, Acceptance Pipeline Specification, Speckit-style layered specs и three-lens review pattern, популяризированный историческим workflow Claude Code `/simplify`.

## Validation

Запустите:

```bash
python3 codex-migration-task/validators/validate_codex_migration.py .
python3 -m unittest discover plugins/engineer/scripts
python3 -m json.tool .codex/hooks.json >/dev/null
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
find plugins -path '*/.codex-plugin/plugin.json' -print -exec python3 -m json.tool {} \; >/dev/null
find plugins -path '*/hooks/*.json' -print -exec python3 -m json.tool {} \; >/dev/null
```

Historical migration evidence не входит в release package, если maintainer явно не включает его для audit.
