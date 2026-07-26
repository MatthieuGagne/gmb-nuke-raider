---
name: grill-with-docs
baseline: grill-with-docs@2026-07-26
---

Project (Nuke Raider) additions and overrides for the baseline grill-with-docs skill. On conflict, this overlay wins.

**What the baseline actually is:** a thin wrapper installed at `~/.claude/skills/grill-with-docs/` (from `mattpocock/skills`, `skills/engineering/grill-with-docs`). It does one thing — run a `/grilling` session using the `/domain-modeling` skill. Both dependencies are installed alongside it (`~/.claude/skills/grilling/`, `~/.claude/skills/domain-modeling/`); if either is missing the wrapper is inert, so reinstall rather than improvising. It is marked `disable-model-invocation: true`, so it runs only when the user invokes it explicitly.

## Project additions

### Grill dimensions

Beyond the baseline's general stress-testing, every grill in this project must cover:

- **Requirements** — what must be true for this to be done.
- **Acceptance criteria** — concrete, checkable, numbered.
- **Scope boundaries** — what is explicitly *out* of scope, recorded as such.
- **GB hardware constraints** — WRAM, VRAM, OAM, and ROM bank budgets; SM83/SDCC limits. A design that has not been costed against these budgets has not been grilled.

### Explore before asking

If a **fact** can be found by exploring the codebase or environment, look it up instead of asking. The **decisions** are the user's — put each one to them and wait. For anything spanning more than 2 files or any open-ended search, dispatch the Explore agent rather than accumulating inline reads.

### Paper trail — versioned in-repo, not in chat

This is the one class of design artifact this project keeps as local files:

- **Glossary / domain context** → `CONTEXT.md` at the repo root. Glossary only — totally devoid of implementation details. It is not a spec, not a scratchpad, not a decision log.
- **Decisions** → ADRs at `docs/adr/NNNN-title.md`, offered sparingly: only when the decision is hard to reverse, surprising without context, AND the result of a genuine trade-off. If any of the three is missing, skip the ADR.
- Use the baseline's `CONTEXT-FORMAT.md` and `ADR-FORMAT.md` for both.
- **Both are written inside the worktree and merged via PR** — never edited directly in the main working tree, never committed straight to `master`.

### PRDs stay on GitHub

The grill's output feeds the `prd` skill, which files a **GitHub issue**. Never write a local PRD file. `CONTEXT.md` and `docs/adr/` are the *only* design artifacts that live in the repo — requirements and feature specs do not.

### Tone

Feature and copy decisions are grilled against `docs/game/game-design.md` — post-apocalyptic wasteland, sparse dry humor, every word earns its place.
