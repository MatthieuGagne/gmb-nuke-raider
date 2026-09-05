# Overlay baseline audits

Authoring provenance for the overlays in `.claude/skill-overlays/`, moved out of the overlay
bodies so it is not injected on every dispatch (#527 R6). The enforceable pin is each overlay's
`baseline:` frontmatter, which `tools/skill_overlay_hook.py` version-checks; the lines below
record when a human last read the baseline text itself and compared it.

- **brainstorming** — content of `superpowers@6.3.0` read and compared on 2026-08-22 (#527 R6).
  6.3.0 restructured the skill around three paths (**spike / bounded / architectural**), each
  with its own checklist and its own terminal state. The overlay's bullets are written against
  that structure.
- **dispatching-parallel-agents** — content of `superpowers@6.3.0` read and compared on
  2026-08-22 (#527 R6). 6.3.0's `SKILL.md` is **byte-identical** to 6.2.0's, so every section
  was re-checked against unchanged text and none was absorbed upstream.
- **executing-plans** — content of `superpowers@6.3.0` read and compared on 2026-08-22 (#527 R6).
  6.3.0's `SKILL.md` is **byte-identical** to 6.2.0's, so every section was re-checked against
  unchanged text and none was absorbed upstream.
- **finishing-a-development-branch** — content of `superpowers@6.3.0` read and compared on
  2026-08-22 (#527 R6). 6.3.0's only change here: a new block on **refused worktree removal**,
  which the overlay keeps inline because it carries a rule.
- **grill-with-docs** — content of `grill-with-docs@2026-07-26` re-read and compared on
  2026-08-22 (#527 R6). This pin is date-based and the hook cannot check it; the overlay keeps
  that consequence inline.
- **subagent-driven-development** — content of `superpowers@6.3.0` read and compared on
  2026-08-22, not merely the version pin (#527 R6). 6.3.0 is a substantial rewrite of the
  controller's authority — see the overlay's `### The fifth stop`, the one place it collides
  with this project.
- **writing-plans** — content of `superpowers@6.3.0` read and compared on 2026-08-22 (#527 R6).
  6.3.0's only change here: a `**Spec:**` field added to the plan header; the overlay keeps the
  mapping to `**Issue:** #N` inline.
