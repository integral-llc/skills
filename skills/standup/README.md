# standup skill

Generates a morning standup from Claude Code conversation history for the current project.

## Install

Drop this whole folder into one of:

- `~/.claude/skills/standup/` (personal, available in every project)
- `<project>/.claude/skills/standup/` (project-scoped, sharable via git)

Personal install is the right call for this skill. Run it from any project root and it picks up that project's CC history.

```bash
cp -r standup ~/.claude/skills/
```

After install, the next CC session in any project will see the skill listed under `<available_skills>` in the system prompt. Trigger it with phrases like "give me a standup", "summarize yesterday", "weekly recap", "what did I do last week", "morning standup notes".

## What it does

1. Runs `scripts/collect.py` against `~/.claude/projects/<encoded-cwd>/*.jsonl` for the requested date window.
2. Reads the last 7 standup files in `.standups/` to find unresolved questions and blockers.
3. Reconciles: which prior open items are now closed in today's activity, which are still open.
4. Synthesizes 3 to 5 corporate-style bullets that map back to actual JSONL events.
5. Runs an anti-AI scrub pass (em dashes, banned vocabulary, rule of three, trailing -ing clauses).
6. Writes `.standups/YYYY-MM-DD.md`.
7. Adds `.standups/` to `.gitignore` if missing.
8. Echoes a paste-friendly version to chat.

## Window flags

Pass any one of these via the script (or natural language to the skill):

- `--yesterday` (default if you say nothing)
- `--today`
- `--day 2026-04-30`
- `--from 2026-04-25 --to 2026-04-30`
- `--last 7`

## Files

```
standup/
├── SKILL.md                       main skill prompt
├── README.md                      this file
├── scripts/
│   └── collect.py                 reads CC JSONL, filters by date, condenses output
└── references/
    ├── anti-ai-rules.md           em dash and AI vocabulary scrub rules
    ├── corporate-bluff.md         vocabulary mapping (broken thing -> stabilized X)
    └── template.md                output file format
```

## Known edge cases

- **No CC history**: if the encoded project dir does not exist, the script exits 2 and the skill tells the user. No fabrication.
- **Empty window**: if the date window has no qualifying turns, the skill stops and reports it. No filler bullets.
- **Project moved or renamed**: the encoded path will not match. The script's fallback walks `~/.claude/projects/` and token-matches. If still nothing, the user has to point at the right encoded name manually.
- **Sessions across timezones**: timestamps in JSONL are UTC. The window is interpreted as UTC. If you want local-time precision, add `--from`/`--to` with explicit dates.
- **Massive day**: turns longer than 1800 chars are truncated. Tool results (which are huge) are dropped entirely. If you need full fidelity, read the JSONL directly.

## Hard rules baked in

- No em dashes anywhere in output.
- No "delve", "leverage", "robust", "seamless" or 18 other banned words.
- 3 to 5 bullets, never more.
- Standup file is never longer than 30 lines.
- Prior standup files are append-only; this skill never edits them.
- The user controls git; this skill never commits.

## Calibration

Read `references/corporate-bluff.md` for the vocabulary mapping. The "good" and "bad" examples there are the calibration target. If a generated bullet does not match the "good" examples, regenerate.
