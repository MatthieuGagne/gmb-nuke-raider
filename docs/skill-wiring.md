# Skill & agent wiring

Imported by [`CLAUDE.md`](../CLAUDE.md). Needed when touching skills, skill overlays, or the
factory — not on a typical code turn.

Agents live in `.claude/agents/`, skills in `.claude/skills/`. Each file's frontmatter
(`description` / when-to-use) is the authoritative trigger and is surfaced automatically; don't
duplicate those descriptions elsewhere. [`docs/dev-workflow.md`](dev-workflow.md) is
co-authoritative and maps each one to its workflow step.

Three things not obvious from frontmatter alone:

- The superpowers workflow skills (brainstorming, writing-plans, executing-plans,
  subagent-driven-development, finishing-a-development-branch, dispatching-parallel-agents)
  run from their auto-updating baselines; project deltas live in
  `.claude/skill-overlays/<name>.md` and are injected automatically by
  `tools/skill_overlay_hook.py` (PostToolUse on Skill + UserPromptSubmit hooks in
  `.claude/settings.json`). On conflict, the overlay wins. Each overlay's `baseline:`
  frontmatter pins the superpowers version it was written against; the hook warns when
  the installed version has moved (re-sync the overlay when it fires). `grill-with-docs` also
  has an overlay, but its baseline is a local skill pinned by date, which the hook cannot
  version-check. **The overlay hook is not ported to Pi or omp** — under those harnesses
  overlays never inject, so read `.claude/skill-overlays/<name>.md` yourself.
- `grill-with-docs` carries `disable-model-invocation: true`, so a model-driven session can never
  reach it. When a decision needs an ADR, ask the user to run it.
- `factory` (`.claude/skills/factory/`) is the unattended orchestrator. It is invoked
  explicitly (`/factory <issue#>` under Claude Code) and never fires automatically. It writes run
  state only through `tools/factory_event.py` and publishes to GitHub only through
  `tools/factory_publish.py` — never directly.
