# ATDD Codex Plugin

Acceptance Test Driven Development workflows for Codex CLI.

This plugin preserves the DAE acceptance discipline:

- write domain-level Gherkin specs before implementation;
- generate a project-specific acceptance pipeline from a fixed IR;
- keep acceptance tests and unit tests as independent streams;
- audit specs for implementation leakage;
- run differential mutation testing as a test-quality firewall;
- use fresh per-phase agent work for long feature implementation.

## Skills

| Skill | Purpose |
|---|---|
| `atdd` | Write Gherkin `spec.md`, parse it to `.build/spec.json`, and create/update the acceptance pipeline. |
| `atdd-team` | Orchestrate fresh per-phase agents for spec, review, pipeline, implementation, refine, and verify/harden. |
| `atdd-mutate` | Set up and run mutation testing, preferring project-specific differential mutation. |
| `spec-check` | Audit specs for implementation leakage using the deterministic checker and `spec-guardian` when available. |
| `kill-mutants` | Analyze surviving mutants and add targeted unit tests for non-equivalent survivors. |
| `mutate` | Codex-native compatibility wrapper that delegates to `atdd-mutate`. |

## Pipeline Contract

Specs are source. Generated tests are output.

```text
features/NNN-slug/spec.md
features/NNN-slug/.build/spec.json
features/NNN-slug/.build/generated/
```

`dae_gherkin.py` parses the Gherkin source into the fixed IR. The project-specific generator and step handlers know the application internals, but the Gherkin spec remains domain-level and free of implementation leakage.

## Verification Contract

Both streams must pass:

- acceptance stream: generated from the approved spec;
- unit stream: tests implementation structure directly.

Mutation testing comes after a green baseline. Differential mutation re-runs only functions whose code, covering tests, or mutation operator set changed, then updates the mutation manifest.

## Hooks

The plugin ships advisory hooks in `hooks/hooks.json`. They warn before source writes without specs and remind after tool use that both streams need verification. Hooks prefer `PLUGIN_ROOT` and `PLUGIN_DATA`; legacy env vars are fallback-only for compatibility.

## Inputs, Outputs, and Limits

Inputs are feature intent, approved ACs, Gherkin specs, and a target repository. Outputs are `spec.md`, `.build/spec.json`, generated acceptance artifacts, unit tests, mutation manifests, and handoffs when used with the team workflow. The portable parser is deterministic; the project-specific test generator depends on the target codebase and must be reviewed like normal source.
