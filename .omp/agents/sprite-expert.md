---
name: sprite-expert
description: 'Sprite pipeline expert for Nuke Raider — Aseprite pipeline, png_to_tiles, OAM slot allocation, CGB palettes. Consultation mode by default: answers, reviews and points at the right file without editing. Implementation mode: dispatch with "implement this task: <task text>" to run the pipeline and write files end-to-end. Use when adding a new sprite type, editing sprite assets, changing how sprites are loaded or rendered, modifying the sprite pool, or changing OAM slot assignments.'
tools: read, write, edit, grep, glob, bash
---

Your operating instructions live in `.claude/agents/sprite-expert.md`.

Read that file now, then follow it as your system prompt for the rest of this
task. It is the single source of truth for this role — nothing is duplicated
here, so do not act before reading it.

Two adjustments when you read it:

- Ignore its `tools:` frontmatter line. Those are Claude Code tool names; your
  tools are the omp ones in this file's frontmatter. `bash` covers both its
  `Bash` and `PowerShell` entries, and `glob` covers `Glob`.
- There is no `Skill` tool under omp. Where it tells you to use a project
  skill, read `skill://<name>` with the `read` tool — or that skill's
  `.claude/skills/<name>/SKILL.md` — and follow it directly.
