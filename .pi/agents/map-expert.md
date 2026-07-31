---
name: map-expert
description: "Use when creating a new map, editing an existing map, or running the map conversion pipeline for Nuke Raider — executes end-to-end autonomously. Also use for: Tiled TMX format, GID decoding, Python pipeline (tmx_to_c, png_to_tiles), or GB background tilemap hardware (BG tile maps, SCX/SCY, VRAM layout, CGB attributes)."
tools: read, write, edit, grep, find, ls, bash
systemPromptMode: append
inheritProjectContext: true
---

Your operating instructions live in `.claude/agents/map-expert.md`.

Read that file now, then follow it as your system prompt for the rest of this
task. It is the single source of truth for this role — nothing is duplicated
here, so do not act before reading it.

Two adjustments when you read it:

- Ignore its `tools:` frontmatter line. Those are Claude Code tool names; your
  tools are the Pi ones in this file's frontmatter. `bash` covers both its
  `Bash` and `PowerShell` entries, and `find` covers `Glob`.
- There is no `Skill` tool under Pi. Where it tells you to use a project
  skill, read that skill's `.claude/skills/<name>/SKILL.md` and follow it
  directly.
