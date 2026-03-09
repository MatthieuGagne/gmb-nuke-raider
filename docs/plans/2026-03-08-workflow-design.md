# Design: Development Workflow Integration with Superpowers

**Date:** 2026-03-08
**Status:** Approved

## Goal

Replace the custom PRD-driven workflow with Superpowers' brainstorm → write-plans → subagent-driven-development loop, retaining only GBC-specific skills and infrastructure.

## What Changes

### Removed
- `.claude/skills/done.md` — covered by Superpowers `finishing-a-development-branch`
- `.claude/skills/prd.md` — covered by Superpowers `brainstorming` + `writing-plans`
- `.claude/skills/build.md` — replaced with proper skill format
- `.claude/skills/test.md` — replaced with proper skill format
- `docs/prd/TEMPLATE.md` / `docs/prd/` directory

### Added
- `.claude/skills/build/SKILL.md` — GBC ROM build skill (proper subdirectory format)
- `.claude/skills/test/SKILL.md` — Unity host-side test skill (proper subdirectory format)
- `docs/plans/TEMPLATE.md` — design doc template aligned with Superpowers convention

### Updated
- `CLAUDE.md` — new `## Workflow` section mapping Superpowers stages to GBC commands
- `.claude/agents/gbdk-expert.md` — cross-reference to `/build` and `/test` skills
- `.claude/agents/gb-c-optimizer.md` — cross-reference to `/build` and `/test` skills

## What Stays

- Unity test framework (`tests/unity/` submodule)
- Mock GBDK headers (`tests/mocks/`)
- `make test` Makefile target
- `gbdk-expert` and `gb-c-optimizer` project agents
- GitHub Actions CI (`.github/workflows/build.yml`)

## Workflow (post-integration)

**Outer loop (Superpowers):**
brainstorming → writing-plans → subagent-driven-development → test-driven-development → requesting-code-review → finishing-a-development-branch

**GBC-specific seams:**
- TDD red/green command: `make test`
- Build verification: `GBDK_HOME=/home/mathdaman/gbdk make`
- Hardware questions: `gbdk-expert` agent
- Code review: `gb-c-optimizer` agent

## Design Decisions

- **YAGNI:** Dropped `/done` and `/prd` entirely — Superpowers covers them without GBC-specific logic.
- **Skill format:** Converted to `<name>/SKILL.md` subdirectory format required by Superpowers/Claude Code.
- **Docs convention:** `docs/plans/` aligns with Superpowers' design doc output path.
