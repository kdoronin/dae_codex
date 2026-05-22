---
name: atdd
description: Checkpoint 3 bridge that turns ACs into Gherkin specs and hands off to the ATDD acceptance pipeline workflow.
---

# atdd

The DAE pipeline's Checkpoint 3 (Spec) entry point. AC discovery (Checkpoint 2,
`discover-acs`) decided *what behaviors must work*; this step formalizes them as
a standard-Gherkin `spec.md` and generates the project-specific test pipeline.

This skill is a **thin bridge**: the acceptance workflow itself lives in the
`atdd` plugin (`atdd` plugin `atdd` skill). `engineer plugin atdd skill` wraps it with the DAE checkpoint
contract — the entry gate in, the handoff out — so the acceptance pipeline is a
first-class checkpoint of the engineer pipeline rather than a separate detour.

**Requires the `atdd` plugin.** If it is not installed, tell the user to install
the `atdd` plugin from the Disciplined Agentic Engineering Codex marketplace and stop.

## When to use

Checkpoint 3, after `discover-acs` (Checkpoint 2) has produced an approved
`acs.md`. Produces `spec.md` + the feature's `.build/` pipeline.

**Not for:** AC discovery (`discover-acs`); planning (`plan`); using the
acceptance workflow outside a DAE feature folder (invoke `atdd` plugin `atdd` skill directly).

## Workflow

### Step 0 — Entry gate

Verify the prior checkpoint is complete: run
`${PLUGIN_ROOT}/scripts/dae_handoff.py <feature-dir> --through 2`. On a
non-zero exit, **stop** and surface the gap to the human.

Verify branch hygiene: run `${PLUGIN_ROOT}/scripts/dae_branch.py <feature-dir>`.
On a non-zero exit, **stop** and surface the message to the human — switch
branches and re-invoke. The check honors the `git.manual: true` manifest
opt-out.

After the gate passes, show the **pipeline breadcrumb**: run
`${PLUGIN_ROOT}/scripts/dae_progress.py <feature-dir>` and present its
output to the human — it shows where this checkpoint sits in the DAE pipeline.
The breadcrumb is advisory: a non-zero exit or a missing `progress.md` never
blocks the skill. Then create one Codex plan item per workflow step below. See
`${PLUGIN_ROOT}/references/progress-indicator.md`.

### Step 1 — Run the acceptance workflow

Invoke the `atdd` plugin `atdd` skill skill, scoped to this feature: write the feature's
`spec.md` in standard Gherkin from `acs.md`, then generate the test pipeline
(the `pipeline-builder` agent + the portable `dae_gherkin.py` parser). Present
`spec.md` to the human for approval — specs are the human's contract.

### Step 2 — Handoff

Emit a summary per `${PLUGIN_ROOT}/references/handoff-summary.md`.
`checkpoint: 3`; the `exit_criteria` block asserts Checkpoint 3's criteria
(Foundation Design Section 8) — `spec.md` parses to a valid IR, every AC maps to
≥1 scenario, spec-check passes — each with `verified_by` and evidence.
`recommended_next`: "use the engineer plugin's plan skill".

## References

- [Foundation Design](https://www.notion.so/3585ecdee0e2811bbc67ff4913c03207) —
  the Checkpoint Exit Contract (Section 8)
- `atdd` plugin `atdd` skill — the acceptance workflow this skill bridges to
