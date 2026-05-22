---
name: crap-analyzer
description: Analyze changed code for complex, under-tested functions using CRAP scoring; produce ranked refactor and test recommendations.
---

# CRAP Analyzer

CRAP (Change Risk Anti-Patterns) flags functions that are both **complex** and **poorly tested** — the worst-risk code to ship.

```
CRAP(m) = comp(m)² × (1 − cov(m))³ + comp(m)
```

This skill scopes analysis to a diff, ranks findings worst-first, and turns each finding into a concrete refactor + test-stub proposal.

When DAE runtime quality gates are active, CRAP evidence is mandatory by default after implementation-affecting edits. Write machine-readable gate evidence to `features/<feature>/evidence/quality/crap.json` and validate it with `python3 plugins/engineer/scripts/dae_guard.py quality-verify` before completion or release.

## Workflow

1. **Determine the diff.** First that works:
   - `gh pr diff` / `gh pr diff <number>` if a GitHub PR is referenced.
   - `git diff --merge-base <main-branch>` — detect the main branch with `git remote show origin | grep 'HEAD branch'`.
   - `git diff --cached` for staged changes.
   - `git diff HEAD~N..HEAD` for a named commit range.
   - Explicit file list if the user names files.

   Pipe the diff to `scripts/compute_crap.py --diff -`.

2. **Locate or generate coverage.** Let the script auto-discover coverage files first (lcov, Cobertura, JaCoCo, Clover, Go `coverage.out`, coverage.py JSON). If nothing is found, follow [references/coverage-discovery.md](references/coverage-discovery.md) to detect the toolchain, then ask before running it. On decline, proceed with coverage=0% and flag it in the report header.

3. **Run the analyzer.**
   ```bash
   python3 <skill-dir>/scripts/compute_crap.py --diff - --repo-root <repo> --threshold <N> --format both
   ```
   Default threshold is 20. Read `.crap-analyzer.json` at repo root if present and pass its `threshold` through. Full flag list and output JSON shape: [references/script-reference.md](references/script-reference.md).

   For DAE quality gates, use the strict policy thresholds unless project config explicitly relaxes them with audit fields:
   - fail at `max_crap_score >= 30`;
   - warn at `max_crap_score >= 20`;
   - require explicit coverage evidence in strict mode;
   - fail if high-risk findings exceed 0.

   Evidence shape:

   ```json
   {
     "schema_version": 1,
     "gate": "crap",
     "tool": "crap-analyzer",
     "status": "PASS",
     "generated_at": "2026-05-22T00:00:00Z",
     "feature": "features/001-demo",
     "changed_files": ["src/app.py"],
     "coverage_source": "coverage.xml",
     "thresholds": {
       "max_crap_score": 30,
       "warn_crap_score": 20,
       "missing_coverage_policy": "assume_zero_and_fail_if_threshold_exceeded",
       "max_high_risk_findings": 0
     },
     "summary": {
       "changed_functions": 1,
       "max_crap_score": 8.0,
       "high_risk_findings": 0
     },
     "findings": []
   }
   ```

4. **Present the report.** Show the markdown table. For each finding, link `file:start_line`. If more than ~8 findings, surface the top 5 and mention the rest.

5. **Propose fixes per finding, worst-first.** For each function above threshold:
   - **Read the function.** Score alone is not enough — look at the code.
   - **Refactor proposal.** Extract-method diff or guard-clause rewrite. Patterns: [references/refactor-patterns.md](references/refactor-patterns.md).
   - **Test stubs.** Cover each uncovered branch in the repo's test framework. Templates: [references/test-stub-templates.md](references/test-stub-templates.md).
   - **Respect codebase conventions.** Read nearby code and match naming, error handling, DI, async patterns.

   When `len(findings) >= 3`, dispatch one subagent per finding in a **single message** — per-finding work is independent so parallelizing drops wall-clock from O(n) to O(1). Prompt template + aggregation rules: [references/subagent-prompt.md](references/subagent-prompt.md). After subagents return, sort by CRAP descending and sanity-check every "safe to auto-apply" claim against step 7.

6. **Present the wrap-up menu.** Dispatch refactor / test-stub work via `prompt the user`. Menu structure and apply loop: [references/wrap-up-menu.md](references/wrap-up-menu.md). "Safe refactor" = pure extract-method with no behavior change (same inputs → same outputs, same side effects, same order). One Edit per action; confirm each before applying.

7. **Never auto-apply:**
   - Changes that reorder side effects or async operations (`await`, `.then`, `subscribe`, promise chains, RxJS / coroutine / goroutine ordering).
   - Changes to constructors, initializers, or lifecycle hooks.
   - Changes to reactive / stream operator ordering.
   - Template / markup / view changes — the script doesn't analyze those.

## Report format

```markdown
### 1. `file.py:42` — `do_thing` (CRAP 240)

**Why it's flagged:** complexity 15, coverage 0% (no tests touching body).

**Refactor proposal:**
<unified diff or code block>

**Test stubs to add:**
<framework-appropriate test block>
```

Keep each section tight — one paragraph of "why", diff, stubs. No preamble.

## Config file

Optional `.crap-analyzer.json` at repo root:

```json
{ "threshold": 20 }
```

Read if present, pass `--threshold` to the script. No other keys for now.

## When not to use this skill

- Analyzing a full codebase unprompted — scope is diff-only by design.
- Running as a standalone CI replacement. In DAE runtime, the analyzer produces evidence and `engineer` owns the cross-plugin blocking gate.
- Files the script doesn't recognize. Supported extensions listed in [references/script-reference.md](references/script-reference.md); binaries, generated code, and config files are skipped automatically.
