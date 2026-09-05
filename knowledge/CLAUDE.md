# Knowledge Wiki — nuke-raider

Project knowledge base for the **nuke-raider** Game Boy game.

**Layout and maintenance rules are cross-project and live in exactly one place:**
`C:\Code\knowledge\CLAUDE.md`. Read it before adding or editing a page — it defines the
`*.md` / `raw/` / `index.md` / `log.md` layout and every maintenance rule (one concept per page,
`summary:` frontmatter, index-in-the-same-edit, wikilinks, `raw/` sources, `log.md` append, graph
regeneration). This wiki uses that layout unchanged; `raw/` is created here on first use.

## Scope

Durable knowledge specific to this project — GBDK/SDCC gotchas as they bite this codebase, engine
architecture, tooling behaviour, "why the code is this way" facts. Cross-project knowledge does
NOT belong here; it goes in the shared wiki at `C:\Code\knowledge\`. Small session-loaded facts
(user preferences, workflow corrections, active work state) stay in the Claude Code memory store,
not here.

## Scope test

"Would this fact matter in a different project?" Yes → `C:\Code\knowledge\`. No → here.
"Must this be auto-loaded to avoid a mistake mid-session?" Yes → memory store, not here.
