# Knowledge Wiki — Schema (nuke-raider)

Project knowledge base for the **nuke-raider** Game Boy game, following the Karpathy
LLM-wiki pattern (https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
Scope: durable knowledge specific to this project — GBDK/SDCC gotchas as they bite this
codebase, engine architecture, tooling behaviour, "why the code is this way" facts.
Cross-project knowledge does NOT belong here — it goes in the shared wiki at
`C:\Code\knowledge\` using this same layout. Small session-loaded facts (user
preferences, workflow corrections, active work state) stay in the Claude Code memory
store, not here.

## Layout

- `*.md` — one concept per page, cross-linked with `[[wikilinks]]`
- `raw/` — immutable source material (articles, transcripts, data); add-only, never edit; created on first use
- `index.md` — the catalog: EVERY page listed under exactly one category heading
- `log.md` — chronological log: date, page(s) touched, one-line why

## Maintenance rules

- One concept per page. If a page grows to cover two ideas, split it and cross-link.
- Every page starts with frontmatter: `summary:` (one line, written with the words you'd
  actually search for — aliases and codenames included) and optional `tags:`.
- Every page is indexed in `index.md` in the same edit that creates it; every index line
  points to a real page. An unindexed page is invisible.
- Link liberally: `[[page-name]]` for every related concept. A link to a page that doesn't
  exist yet marks something worth writing — it is not an error.
- Don't record what code, git history, or the project's own docs already state — link to
  them instead.
- Sources go in `raw/` unmodified; wiki pages cite them with a relative link.
- Append one line to `log.md` on every substantive change.

## Scope test

"Would this fact matter in a different project?" Yes → `C:\Code\knowledge\`. No → here.
"Must this be auto-loaded to avoid a mistake mid-session?" Yes → memory store, not here.
