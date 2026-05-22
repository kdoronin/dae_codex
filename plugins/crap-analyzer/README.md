# CRAP Analyzer Codex Plugin

Changed-code risk analysis for Codex CLI.

CRAP (Change Risk Anti-Patterns) flags functions that are both complex and poorly tested:

```text
CRAP(m) = comp(m)^2 * (1 - cov(m))^3 + comp(m)
```

The plugin scopes analysis to a diff, auto-discovers coverage when possible, ranks risky functions, and proposes safe refactors plus test stubs.

## Skill

| Skill | Purpose |
|---|---|
| `crap-analyzer` | Analyze changed code, compute/rank CRAP findings, and propose targeted refactors and tests. |

## Supported Languages

TypeScript, JavaScript, Python, Java, Kotlin, Go, Ruby, C#, Rust, and PHP.

## Coverage Discovery

The skill first uses existing coverage artifacts when present: lcov, Cobertura, JaCoCo, Clover, Go `coverage.out`, and coverage.py JSON. If no artifact is found, it inspects the repository's own scripts and asks before running coverage generation. If coverage is unavailable or declined, findings use `coverage=0%` and state that limitation.

## Safety Rules

- Scope to changed code unless the user explicitly asks for a wider audit.
- Prompt before running tests or applying edits.
- Prefer safe extract-method or guard-clause refactors.
- Do not auto-apply changes that reorder side effects, async operations, constructors, lifecycle hooks, stream chains, or UI templates.
- Treat test stubs as proposals unless the user asks to add them.

## Inputs, Outputs, and Limits

Inputs are a git diff or explicit file scope plus optional coverage artifacts. Output is a ranked markdown/JSON report naming risky functions, complexity, coverage, CRAP score, and concrete refactor/test ideas. The analyzer is heuristic and diff-scoped; it is a decision aid, not a replacement for language-specific static analysis.
