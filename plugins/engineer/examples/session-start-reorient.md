# Example: auto-reorient on context compaction

Optional project config. When Codex CLI compacts the context, this hook nudges
the agent to run `engineer plugin -> reorient skill` before continuing feature work.

Add to a trusted project's Codex hook configuration when the current Codex hook
schema supports `SessionStart`:

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

Create `.codex/hooks/reorient-nudge.sh` (make it executable with `chmod +x`):

```sh
#!/bin/sh
# SessionStart hook — on a context compaction, nudge a DAE re-anchor.
input=$(cat)
case "$input" in
  *'"source":"compact"'*)
    printf '%s' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Context was compacted. Run engineer plugin -> reorient skill before continuing feature work — restore role, current checkpoint, exit criteria, and the next action."}}'
    ;;
esac
```

The hook script checks the `source` field itself, so it stays silent on normal
startup/resume and only fires after a compaction.
