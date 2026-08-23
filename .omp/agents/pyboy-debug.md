---
name: pyboy-debug
description: 'TRIGGER when: automated headless diagnosis needed, no GUI available, want a no-interaction alternative to emulicious-debug. Accepts a bug description; boots the ROM headlessly, reads memory + screenshots, runs unit tests, iterates at least 2 rounds, produces a structured diagnostic. DO NOT TRIGGER when: step-through breakpoints are needed (use emulicious-debug) or compile errors (use gbdk-expert).'
tools: read, write, grep, glob, bash
---

Your operating instructions live in `.claude/agents/pyboy-debug.md`.

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
