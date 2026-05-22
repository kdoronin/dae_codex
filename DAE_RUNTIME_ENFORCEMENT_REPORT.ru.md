# Отчет: принудительное применение DAE-инструкций при инициализации Codex plugin

## Краткий вердикт

Сейчас это не реализовано как принудительное применение всех DAE-инструкций при инициализации плагина.

Реализована комбинация:

- инструкции внутри `SKILL.md`, которые применяются только когда выбран или сработал конкретный skill;
- advisory hooks для `PreToolUse` и `PostToolUse`, в основном по ATDD;
- installer, который включает Codex features и ставит hook bridge;
- deterministic scripts, которые запускаются из workflow, но не автоматически на каждое действие.

Текущая модель: "направлять и напоминать", а не "принудительно зафиксировать весь контракт DAE на уровне runtime".

## Что сейчас есть

### 1. Plugin manifests не содержат глобального init/system contract

В `plugins/engineer/.codex-plugin/plugin.json` есть только `skills`.

В `plugins/atdd/.codex-plugin/plugin.json` есть `skills` и `hooks`.

В `plugins/crap-analyzer/.codex-plugin/plugin.json` есть только `skills`.

Нет отдельной always-on instructions поверхности, которая бы при установке или инициализации плагина заставляла Codex всегда соблюдать DAE pipeline.

### 2. Installer включает hooks/goals, но не вводит полный DAE runtime contract

`scripts/install-codex-dae.sh` устанавливает три плагина:

```bash
codex plugin add "engineer@$MARKETPLACE"
codex plugin add "atdd@$MARKETPLACE"
codex plugin add "crap-analyzer@$MARKETPLACE"
```

Он включает safe features:

```python
for feature in ("hooks", "plugin_hooks", "goals"):
    set_bool(lines, "features", feature, True)
```

Но hook bridge ставится только для двух событий:

```python
replace_event("PreToolUse", "check-specs-exist.sh")
replace_event("PostToolUse", "stop-reminder.sh")
```

Это полезно, но не покрывает `SessionStart`, `UserPromptSubmit`, `PermissionRequest`, `Stop` и не загружает весь DAE-контракт как обязательный runtime context.

### 3. Hook layer сейчас advisory, не hard-blocking

`plugins/atdd/hooks/hooks.json` настраивает:

- `PreToolUse`;
- `PostToolUse`.

`plugins/atdd/hooks/scripts/check-specs-exist.sh` прямо описан как soft warning:

```bash
# PreToolUse hook: soft warning when writing code without specs
```

Даже когда спецификаций нет, script печатает reminder и завершает работу с `exit 0`.

`plugins/atdd/hooks/scripts/stop-reminder.sh` тоже является reminder:

```bash
# PostToolUse hook: remind to verify both test streams after implementation work.
# Codex does not expose the legacy Stop hook one-to-one, so this advisory
# reminder runs after tool use events instead.
```

README фиксирует это явно:

> When a guardrail triggers, it emits Codex hook context rather than deleting or rewriting files. The implementation-before-spec guard is a warning because current Codex hook semantics do not make this plugin a universal hard blocker.

### 4. Большинство правил живет только в skills

Примеры:

- `plugins/atdd/skills/atdd/SKILL.md` говорит: `Follow these steps strictly, in order. Do not skip steps.`
- Там же описан spec-leakage rule: specs must describe external observables only.
- Там же требуется human approval перед продолжением после specs.
- `plugins/engineer/skills/plan/SKILL.md` требует prior checkpoint gate и human approval архитектуры.
- `plugins/engineer/skills/discover-acs/SKILL.md` требует handoff gate и branch hygiene.
- `plugins/atdd/skills/atdd-team/SKILL.md` требует durable handoffs, phase gates и verification independence.
- `plugins/atdd/skills/atdd-mutate/SKILL.md` требует оба test streams перед mutation testing.
- `plugins/crap-analyzer/skills/crap-analyzer/SKILL.md` описывает CRAP flow как Codex-driven review, а не deterministic blocking gate.

Это сильные инструкции, но они не гарантируются, если пользователь просто просит Codex писать код без явного skill или если skill auto-trigger не сработал.

### 5. SessionStart есть только как optional example

`plugins/engineer/examples/session-start-reorient.md` предлагает optional project config:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": ".codex/hooks/reorient-nudge.sh" }
        ]
      }
    ]
  }
}
```

`plugins/engineer/skills/reorient/SKILL.md` говорит, что project may add a `SessionStart` hook. Это не часть установленного runtime по умолчанию.

## Synthetic hook evidence

Были прогнаны текущие hook scripts на синтетических событиях.

### Source write без specs

Команда:

```bash
tmp=$(mktemp -d)
printf '%s' '{"tool_name":"apply_patch","tool_input":{"command":"*** Add File: src/app.py\n+print(1)\n"}}' \
  | CODEX_PROJECT_DIR="$tmp" bash plugins/atdd/hooks/scripts/check-specs-exist.sh
echo "exit=$?"
```

Фактическое поведение:

```json
{"hookSpecificOutput": {"additionalContext": "ATDD reminder: no acceptance specs were found. DAE expects Gherkin spec.md or legacy specs/*.txt before implementation; use the atdd plugin skill to start the workflow."}}
```

Exit code: `0`.

Вывод: нарушение не блокируется, только добавляется reminder context.

### Source write при наличии spec

Команда:

```bash
tmp=$(mktemp -d)
mkdir -p "$tmp/features/001-demo"
touch "$tmp/features/001-demo/spec.md"
printf '%s' '{"tool_name":"apply_patch","tool_input":{"command":"*** Add File: src/app.py\n+print(1)\n"}}' \
  | CODEX_PROJECT_DIR="$tmp" bash plugins/atdd/hooks/scripts/check-specs-exist.sh
echo "exit=$?"
```

Фактическое поведение: output отсутствует.

Exit code: `0`.

### PostToolUse при наличии spec

Команда:

```bash
tmp=$(mktemp -d)
mkdir -p "$tmp/features/001-demo"
touch "$tmp/features/001-demo/spec.md"
printf '%s' '{"tool_name":"apply_patch"}' \
  | CODEX_PROJECT_DIR="$tmp" bash plugins/atdd/hooks/scripts/stop-reminder.sh
echo "exit=$?"
```

Фактическое поведение:

```json
{"hookSpecificOutput": {"additionalContext": "ATDD reminder: before considering this task complete, verify both test streams pass: acceptance tests and unit tests. Both streams must be green."}}
```

Exit code: `0`.

Вывод: hook напоминает о двух test streams, но не проверяет и не блокирует завершение.

## Главные пробелы

1. Нет единого machine-readable DAE contract.

   Правила размазаны по `AGENTS.md`, `README.md`, `SKILL.md`, hooks и scripts.

2. Нет init hook, который при старте сессии инжектит весь DAE contract и текущее состояние фичи.

3. Нет `UserPromptSubmit` guard.

   Сейчас prompt вроде "сделай фичу", "реализуй", "добавь код" не перехватывается системно, чтобы принудительно направить workflow через ACs, specs и plan.

4. Нет `PermissionRequest` guard.

   Нет отдельной проверки против unsafe approvals, dangerous sandbox escalation, approval bypass или destructively risky commands.

5. Нет `Stop` или finish guard.

   Перед завершением сессии не проверяются автоматически:

   - handoff completeness;
   - acceptance tests;
   - unit tests;
   - mutation evidence where required;
   - CRAP/architecture checks;
   - branch/progress breadcrumbs.

6. Hook проверяет только наличие spec.

   Сейчас `check-specs-exist.sh` не проверяет:

   - наличие `feature.md`;
   - acceptance criteria;
   - `plan.md`;
   - human approval markers;
   - checkpoint order;
   - branch hygiene;
   - handoff completeness;
   - spec leakage;
   - generated-test immutability.

7. Manual install path не равен production install path.

   README manual install ставит плагины, но не ставит user-level hook bridge. Надежный bridge делает только `scripts/install-codex-dae.sh`.

8. Enforcement зависит от срабатывания skill или hook.

   Это не то же самое, что "плагин инициализирован, значит все ограничения действуют всегда".

## Идеи реализации

### 1. Ввести единый DAE contract registry

Создать, например:

```text
plugins/engineer/guardrails/dae-contract.yml
```

Или:

```text
plugins/engineer/guardrails/dae-contract.json
```

Каждое правило описать машинно:

```yaml
- id: dae.specs_before_implementation
  severity: blockable
  events:
    - PreToolUse
    - UserPromptSubmit
  detector: scripts/dae_guard.py check-spec-before-write
  message: Implementation requires accepted ACs and Gherkin spec first.
  fallback: advisory_if_codex_cannot_block
```

Туда вынести:

- pipeline order;
- no implementation before acceptance specs;
- no architecture implementation before approved plan;
- human approval for charter and architecture decisions;
- spec leakage guard;
- two independent test streams;
- generated acceptance tests are regenerated, not hand-edited;
- handoff gates;
- branch hygiene;
- progress breadcrumbs;
- mutation workflow;
- CRAP analysis;
- architecture/refine checks;
- duplicate/test-impact checks;
- safe non-destructive behavior.

### 2. Добавить единый runtime guard CLI

Создать:

```text
plugins/engineer/scripts/dae_guard.py
```

Предлагаемые subcommands:

```bash
dae_guard.py session-start
dae_guard.py user-prompt-submit
dae_guard.py pre-tool-use
dae_guard.py post-tool-use
dae_guard.py permission-request
dae_guard.py stop
dae_guard.py doctor
```

Этот CLI должен читать:

- `PLUGIN_ROOT`;
- `PLUGIN_DATA`;
- `CODEX_PROJECT_DIR`;
- `.engineer/manifest.yml`;
- `CHARTER.md`;
- `features/*/feature.md`;
- `features/*/progress.md`;
- `features/*/handoffs/*.md`;
- machine-readable contract registry.

### 3. Расширить hooks

Минимальный целевой набор:

#### `SessionStart`

Инжектит:

- DAE non-negotiables;
- текущий checkpoint;
- текущий feature pointer, если определяется по branch/progress;
- next action;
- blocked state;
- reminder про `reorient` after compaction.

#### `UserPromptSubmit`

Если пользователь просит implementation/build/add feature, hook должен добавить context:

- сначала `engineer -> feature-init`;
- затем `discover-acs`;
- затем `engineer atdd` / `atdd`;
- затем `plan`;
- только потом implementation.

Для prompt, который пытается обойти pipeline, hook должен вернуть строгий warning или block, если Codex API позволяет.

#### `PreToolUse`

Проверяет:

- `Bash`;
- `apply_patch`;
- `Write`;
- `Edit`;
- другие write-capable tools, если доступны.

Если source write происходит до AC/spec/plan, блокировать там, где Codex hook API позволяет; иначе выдавать explicit advisory с пометкой `NOT BLOCKED BY PLATFORM`.

#### `PostToolUse`

После source edits проверяет или напоминает:

- acceptance stream;
- unit stream;
- progress breadcrumb;
- handoff status;
- generated-test immutability;
- spec leakage scan if specs touched.

#### `PermissionRequest`

Проверяет:

- `danger-full-access`;
- approval bypass;
- yolo-style execution;
- destructive shell operations;
- writes outside workspace;
- mutation tools attempting to mutate tests/specs/generated files.

Ожидаемое поведение: deny/block where supported, otherwise structured warning.

#### `Stop`

Если Codex поддерживает event:

- не завершать без session summary/handoff when feature work occurred;
- проверять acceptance/unit evidence;
- проверять CRAP/arch/mutation where required;
- проверять outstanding human decisions.

Если `Stop` недоступен или нет one-to-one mapping, явно документировать fallback через `PostToolUse` и `session-summary`.

### 4. Разделить context injection и hard gates

Важно для ТЗ: не все можно сделать hard-blocking внутри Codex.

Предлагаемая классификация:

| Тип | Поведение |
|---|---|
| Hard gate | Hook/API реально может отклонить действие. |
| Advisory guard | Hook добавляет обязательный context, но действие технически продолжается. |
| Audit-only | Hook пишет evidence в `PLUGIN_DATA`, но не влияет на ход выполнения. |
| Skill gate | Проверка выполняется внутри skill workflow. |
| CI/release gate | Проверка выполняется отдельной командой перед release. |

Каждое правило из contract registry должно иметь явный enforcement mode.

### 5. Сгенерировать project-scoped AGENTS.md при onboard

Во время `engineer onboard` можно предлагать добавить DAE секцию в целевой `AGENTS.md`.

Содержимое:

- DAE pipeline order;
- no implementation before AC/spec/plan;
- two test streams;
- human approval boundaries;
- generated tests not hand-edited;
- mutation/CRAP/arch gates;
- safe permission policy.

Важно: это запись в проект, поэтому она должна требовать user approval.

### 6. Сделать install path одинаково безопасным

Варианты:

1. Считать `scripts/install-codex-dae.sh` единственным production install path.
2. Добавить отдельную команду:

   ```bash
   codex dae init-hooks
   ```

3. В README manual install явно помечать как partial install без full runtime guardrails.
4. Installer должен валидировать, что user-level hooks реально установлены и executable.

### 7. Добавить deterministic verification harness

Потребовать тесты и fixture repos:

- JSON manifest validation;
- synthetic hook probes для всех configured events;
- fixture repo без specs: source write должен block или warn expected образом;
- fixture repo со specs, но без plan: implementation должен block или warn;
- fixture repo с plan, но без approval marker: block или warn;
- fixture repo с implementation, но без acceptance/unit evidence: `Stop`/`PostToolUse` warning;
- unsafe permission request probe;
- `SessionStart` context snapshot;
- `UserPromptSubmit` context snapshot;
- audit log assertions under `PLUGIN_DATA`;
- docs state exactly which rules are hard-blocked and which are advisory.

## Возможная целевая архитектура

```text
plugins/
  engineer/
    .codex-plugin/plugin.json
    guardrails/
      dae-contract.yml
    hooks/
      hooks.json
      scripts/
        dae-session-start.sh
        dae-user-prompt-submit.sh
        dae-pre-tool-use.sh
        dae-post-tool-use.sh
        dae-permission-request.sh
        dae-stop.sh
    scripts/
      dae_guard.py
      dae_contract.py
      dae_state.py
      dae_handoff.py
      dae_branch.py
      dae_progress.py
  atdd/
    hooks/
      hooks.json
      scripts/
        check-specs-exist.sh
        stop-reminder.sh
```

Но лучше избежать разрыва ownership:

- ATDD-specific checks могут остаться в `atdd`;
- cross-DAE lifecycle guardrails лучше держать в `engineer`;
- installer должен bridge-ить оба набора hooks в user-level `~/.codex/hooks.json`, если plugin-local hooks все еще ненадежны.

## Рекомендуемая формулировка для будущего ТЗ

Сделать DAE guardrails always-on после установки/инициализации плагина:

1. Централизовать DAE contracts в machine-readable registry.
2. Добавить единый `dae_guard.py`, который умеет оценивать проектное состояние и hook events.
3. Подключить guard к поддерживаемым Codex hook events:
   - `SessionStart`;
   - `UserPromptSubmit`;
   - `PreToolUse`;
   - `PostToolUse`;
   - `PermissionRequest`;
   - `Stop`, если поддерживается текущим Codex runtime.
4. Расширить installer так, чтобы он ставил runtime hook bridge для полного набора events.
5. Сохранить safe non-destructive default: не включать `danger-full-access`, approval bypass или unsafe permissions.
6. Где Codex hook API позволяет hard block, нарушения должны блокироваться.
7. Где hard block невозможен, output должен явно говорить, что это advisory fallback, и писать audit evidence.
8. Во время onboarding добавить optional project-scoped `AGENTS.md` DAE section с user approval.
9. Покрыть synthetic hook probes и real fixture runtime tests.
10. Обновить README/docs так, чтобы они не обещали hard enforcement там, где реально только advisory.

## Open questions для ТЗ

1. Поддерживает ли текущий Codex hook API реальное deny/block поведение для `PreToolUse`, `UserPromptSubmit`, `PermissionRequest` и `Stop`?
2. Должен ли plugin hard-block source edits до `plan.md`, или только до `spec.md`?
3. Как фиксировать human approval машинно:
   - marker в `handoffs/*.md`;
   - frontmatter в `plan.md`;
   - отдельный `.engineer/approvals.jsonl`;
   - tracker state?
4. Должен ли `SessionStart` всегда инжектить полный DAE contract или только краткий summary плюс ссылку на `reorient`?
5. Должен ли manual install оставаться supported production path?
6. Какой минимальный acceptable fallback, если plugin-local hooks не исполняются текущим Codex CLI?

## Итог

Текущий плагин уже содержит методологические контракты и часть deterministic guardrails, но они не являются always-on enforcement layer.

Для требуемого поведения нужна отдельная runtime-enforcement доработка:

- centralized contract registry;
- unified guard CLI;
- expanded hook coverage;
- installer bridge;
- machine-readable audit log;
- deterministic fixture tests;
- четкая документация hard-block vs advisory.
