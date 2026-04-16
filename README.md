# Claude Code Skills

A collection of reusable [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for software engineering workflows.

## What are Skills?

Skills are markdown-based prompt templates that extend Claude Code with specialized capabilities. Each skill lives in its own directory with a `SKILL.md` file that defines the skill's behavior, phases, and quality gates.

Skills can be invoked via slash commands in Claude Code (e.g., `/implement-a-prd`).

## Available Skills

| Skill | Description |
|-------|-------------|
| [implement-a-prd](./implement-a-prd/) | Implement a PRD with principal-engineer-grade code quality. Discovers project toolchain rules, enforces SOLID/DRY/GoF patterns, and produces code that passes lint, type check, and formatting on first commit. |

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
cp -r implement-a-prd /path/to/your/project/.claude/skills/
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
  SKILL.md    # Skill definition with frontmatter and instructions
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
