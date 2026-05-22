---
name: quality-verify
description: Validate strict DAE quality gates after implementation-affecting changes, require machine-readable evidence, and write the quality-gate summary before completion or release.
---

# DAE Quality Verify

Use this skill when implementation/scaffold/config/test work has happened, when `quality_dirty=true`, or before any completion/release/commit/push claim.

## Contract

Quality verification is evidence-driven. Do not satisfy required gates with prose-only claims.

Strict defaults require:

- ATDD acceptance stream evidence;
- independent unit stream evidence;
- CRAP analyzer evidence;
- architecture check evidence;
- refine review evidence;
- branch hygiene evidence;
- progress breadcrumb evidence;
- durable handoff evidence;
- duplicate-detection evidence;
- test-impact evidence;
- generated acceptance immutability evidence;
- mutation evidence when configured, hardening is active, or CRAP/risk triggers it.

## Workflow

1. Inspect current status:

   ```bash
   python3 plugins/engineer/scripts/dae_guard.py quality-status
   python3 plugins/engineer/scripts/dae_guard.py quality-required-evidence
   ```

2. Produce missing evidence with the owning workflows:

   - `atdd`: acceptance stream, unit stream, generated acceptance immutability, mutation/hardening.
   - `engineer`: arch-check, refine, branch hygiene, progress, handoff, duplicate detection, test impact.
   - `crap-analyzer`: CRAP scoring for changed code.

3. Write evidence under:

   ```text
   features/<feature>/evidence/quality/<gate>.json
   ```

   Every required evidence file must include `schema_version`, `gate`, `status`, `generated_at`, `feature`, and `changed_files`.

4. Validate and summarize:

   ```bash
   python3 plugins/engineer/scripts/dae_guard.py quality-verify
   ```

5. Continue only if `quality-verify` exits 0 and writes a passing `quality-gate-summary.json`.

## CRAP Evidence

CRAP is required by default after implementation-affecting edits. Missing coverage must not silently pass strict mode. The CRAP evidence file must include thresholds and summary fields, including `summary.max_crap_score` and `summary.high_risk_findings`.

If CRAP returns warning-level risk or high-risk findings, mutation evidence becomes required before completion.
