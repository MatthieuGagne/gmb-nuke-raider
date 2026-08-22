---
name: emulicious-debug
description: 'TRIGGER when: any runtime crash, unexpected in-game behavior, visual glitch, wrong values at runtime, or need to inspect memory/tiles/sprites/palettes/ROM layout during execution. DO NOT TRIGGER when: the problem is a compile error (use gbdk-expert) or static code review (use gb-c-optimizer).'
tools: read, edit, grep, glob, bash
---

Your operating instructions live in `.claude/agents/emulicious-debug.md`.

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
