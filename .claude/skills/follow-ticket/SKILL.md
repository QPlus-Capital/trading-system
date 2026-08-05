---
name: follow-ticket
description: Invoke in a ticket's chat to follow its run live and narrate every change in German.
---

The ticket chat pulls; nothing pushes into it. The review cycle only appends events to the
ticket's log, and this skill makes the chat the operator is actually looking at watch the run and
tell them what happens — with the artifacts read, not paraphrased from an event line.

## Required inputs

- The issue number. The chat that specified the ticket follows it after the release; any fresh
  chat the operator points at a ticket may follow it too.

## Procedure

1. Start the watcher **in the background** and let the session be woken on every state change:

   ```
   uv run python -m workflow.watch <issue> --until-change --max-minutes 45
   ```

2. On each wake-up, read what actually changed before writing a word: the snapshot names the
   card, head, checks, review count and event count — follow them to the sources you need
   (`gh pr view --json reviews`, `gh run view`, the event log named by
   `workflow.orchestrate.events_path`, `just board status`). Never narrate an event line alone
   when the artifact behind it says more.
3. Write the update for the operator in German. No fixed template — say what the moment needs —
   but every update anchors its facts (ticket, phase or round, commit where it matters), says
   what happened, what it means, and what comes next or what the operator must do; a command
   stands on its own line; a decision is set off visibly with its question, options,
   recommendation, and the default if nothing is decided. Never invent detail, never pad.
4. Re-arm the watcher (step 1) after every update. On a timeout wake-up with nothing changed,
   re-arm silently — unless something long is running, then one line of heartbeat with its age.
5. **When the pull request merges, write the closing summary before anything else ends:** every
   advisory finding from every round, every decision still open — each with recommendation and
   default — and, for findings worth a ticket, a ready-to-paste prompt the operator can open a
   fresh chat with. Decisions must not vanish into a closed pull request; repeat the open ones
   until the operator has answered, and remind them of `just finish <issue>` once the merge is
   in. Then stop watching.

## Outputs

- German narration in the ticket's own chat, one update per real change, decisions kept alive
  until answered, and a closing summary that survives the merge.

## Stop conditions

- Stop watching when the ticket is merged, torn down, and the closing summary is delivered.
- Stop and tell the operator when the watcher itself cannot run — a silent watch is worse than
  none.

## Prohibited shortcuts

- Do not act on the run: no builds, no fixes, no board moves the contract does not assign to
  this chat, no merges. Watching is read-only.
- Do not summarise findings from memory; read the review that states them.
- Do not let a wake-up pass unnarrated when the state moved — the operator follows the ticket
  here, not on GitHub.
