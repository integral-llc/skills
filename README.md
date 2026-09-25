# Claude Code Skills

A collection of reusable [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for software engineering workflows.

## What are Skills?

Skills are markdown-based prompt templates that extend Claude Code with specialized capabilities. Each skill lives in its own directory with a `SKILL.md` file that defines the skill's behavior, phases, and quality gates.

Skills can be invoked via slash commands in Claude Code (e.g., `/implement-a-prd`).

## Available Skills

| Skill | Description |
|-------|-------------|
| [implement-a-prd](./skills/implement-a-prd/) | Implement a PRD with principal-engineer-grade code quality. Discovers project toolchain rules, enforces SOLID/DRY/GoF patterns, and produces code that passes lint, type check, and formatting on first commit. |
| [write-a-prd-local](./skills/write-a-prd-local/) | Create a PRD through user interview, codebase exploration, and module design, stored locally in the repo. |
| [improve-codebase-architecture](./skills/improve-codebase-architecture/) | Explore a codebase, surface architectural friction, and propose module-deepening refactors as GitHub issue RFCs. |
| [improve-codebase-architecture-advanced](./skills/improve-codebase-architecture-advanced/) | Metrics-driven variant: combines qualitative exploration with quantitative metrics to propose deeper module refactors as GitHub issue RFCs. |
| [standup](./skills/standup/) | Generate a morning standup from Claude Code conversation history. Reconciles prior `.standups/` for carry-forward items, produces 3 to 5 corporate-style bullets, scrubs AI tells (em dashes, banned vocabulary), writes `.standups/YYYY-MM-DD.md`. |
| [code-harden](./skills/code-harden/) | Produce code that survives senior review. Drafts, critiques against a fixed rubric, gates critiques by concrete failure mode, iterates 2-3 times max, outputs final code plus a decisions changelog. |
| [pr-review](./skills/pr-review/) | Evidence-based PR review: CI gate that checks green is real, risk-ordered reading, function / system / security checklists (T, S, D tables), every required finding backed by a repro, mutation or call site, comments tagged `[r]`/`[o]`/`[f]`/`[c]`. |
| [pr-post-comments](./skills/pr-post-comments/) | Post review findings and replies to a PR one at a time, paced by comment length, through a bundled driver that enforces the `[r]`/`[o]`/`[f]`/`[c]` tags and a voice lint. Dedupes against bot reviewers, drafts for approval first. |
| [pr-verify-review](./skills/pr-verify-review/) | Re-check a teammate's PR after your review: verify each comment is actually solved in code, judge pushback on its merits, scan the delta for regressions, draft follow-ups, post paced on approval. Read-only on their branch. |
| [pr-address-review](./skills/pr-address-review/) | Answer human review feedback on your own PR: validate each claim, fix the valid ones, resolve base conflicts, draft replies, push, post paced, watch CI to green. Never merges, never resolves a reviewer's thread. |
| [model-router](./skills/model-router/) | Route each prompt and Agent delegation to the cheapest Claude tier (haiku / sonnet / opus / fable) that can do it correctly, using Jev (TypeSafe System One) as a calibrated classifier. Hooks stamp the tier on Agent calls; `audit` reads ground truth from transcripts, `doctor` checks aliases and model ids. Keyword fallback offline. |

## Installation

### Add all skills

Clone this repo and add the path to your Claude Code settings:

```bash
git clone git@github.com:integral-llc/skills.git ~/.claude/skills
```

Then add to `~/.claude/settings.json`:

```json
{
  "skills": ["~/.claude/skills"]
}
```

### Add a single skill

Copy the skill directory into your project's `.claude/skills/` directory:

```bash
cp -r skills/implement-a-prd /path/to/your/project/.claude/skills/
```

Or reference it from your project's `.claude/settings.json`:

```json
{
  "skills": ["/absolute/path/to/skills/implement-a-prd"]
}
```

## Skill Structure

Each skill follows this structure:

```
skill-name/
  SKILL.md       # Skill definition with frontmatter and instructions
  REFERENCE.md   # Optional: detailed reference material loaded on demand
```

The `SKILL.md` frontmatter:

```yaml
---
name: skill-name
description: One-line description of what the skill does
---
```

## Contributing

To add a new skill:

1. Create a directory with the skill name (kebab-case)
2. Add a `SKILL.md` with frontmatter (`name`, `description`) and the skill instructions
3. Keep skills focused - one skill, one responsibility
4. Test the skill in a real project before submitting

## Acknowledgments

Some skills in this collection are based on or inspired by skills from [mattpocock/skills](https://github.com/mattpocock/skills).

## License

MIT
