# Standup template

This is the file format for `.standups/YYYY-MM-DD.md`. Fill in the placeholders. Drop sections that are empty (do not include "Carrying forward" if nothing carries forward).

## Layout

```markdown
# Standup {YYYY-MM-DD}

_window: {start} to {end} | {N} sessions | {project name}_

- {bullet 1}
- {bullet 2}
- {bullet 3}
- {bullet 4 if needed}
- {bullet 5 if needed}

## Carrying forward

- {item from prior standup that is still open} _(open since {YYYY-MM-DD})_
- {another}

## Resolved this cycle

- {item from prior standup that closed} _(opened {YYYY-MM-DD}, closed today)_

## Open questions

- {question that needs an answer from a person, team, or decision}
- {another}

---
_generated from `~/.claude/projects/{encoded-path}` over {N} sessions._
```

## Section rules

- **Bullets section is required.** 3 to 5 items. No more, no fewer.
- **Carrying forward is optional.** Only include if items are genuinely still open. Do not pad.
- **Resolved this cycle is optional.** Only include if today's activity actually closed prior items.
- **Open questions is optional.** Only include if there are real questions a teammate or manager needs to act on. "Should I use Postgres or DynamoDB" is a real question. "What is the meaning of life" is not.
- **The bottom footer is required.** It documents source provenance.

## What not to put in the file

- A "summary" paragraph at the top.
- An "achievements" section.
- An "outlook" section.
- Emoji, even for status.
- Time tracking ("spent 3 hours on X").
- Apologies or hedges.

## Chat output (separate from file)

After writing the file, print the bullets only to chat in a paste-friendly format:

```
Standup YYYY-MM-DD

bullet 1 text without any leading marker
bullet 2 text
bullet 3 text
```

No leading dashes, no asterisks, no numbering. One bullet per line. Blank line between the date header and the body. This pastes cleanly into Slack, Teams, or a stand-up bot.
