---
name: spec-check
description: Audit GWT acceptance test specs for implementation leakage. Optionally provide a specific file path.
---

# spec-check

Audit acceptance test specifications for implementation leakage. Use the
deterministic checker first:

```bash
python3 ${PLUGIN_ROOT}/../engineer/scripts/dae_spec_leak.py <path-or-root>
```

If the deterministic checker is unavailable from the installed plugin layout,
use the project custom agent `spec-guardian` when available; otherwise run the
same read-only review directly.

If a file path is provided, review only that file. If no path is provided,
review `features/*/spec.md` and legacy `specs/*.txt`.

Report concrete file/line findings, the leaked implementation term, and a
domain-language rewrite. Do not edit specs unless the user explicitly asks.
