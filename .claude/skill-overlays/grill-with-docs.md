---
name: grill-with-docs
baseline: grill-with-docs@2026-07-26
---

Project (Nuke Raider) additions and overrides for the baseline grill-with-docs skill. On
conflict, this overlay wins — but an override earns that only by stating what the baseline
cannot know (#527 R7).

**Baseline audit:** content of `grill-with-docs@2026-07-26` re-read and compared on 2026-08-22
(#527 R6).

**This pin is date-based and human-verified — the hook cannot check it.** The baseline is **not**
a superpowers skill, so `tools/skill_overlay_hook.py` skips its version canary outright
(`canary_note` returns early for any `baseline:` whose plugin is not `superpowers`). Nothing will
ever warn that this overlay has drifted. The date above therefore means: on that date a human
opened the files below and confirmed the claims. Re-verify by hand, or the pin says nothing.

**What the baseline actually is** (re-confirmed on disk 2026-08-22): a thin wrapper installed at `~/.claude/skills/grill-with-docs/` (from `mattpocock/skills`, `skills/engineering/grill-with-docs`). Its `SKILL.md` is 7 lines — frontmatter plus a one-sentence body: run a `/grilling` session using the `/domain-modeling` skill. Both dependencies are still installed alongside it (`~/.claude/skills/grilling/SKILL.md`, `~/.claude/skills/domain-modeling/SKILL.md`); if either is missing the wrapper is inert, so reinstall rather than improvising. It is still marked `disable-model-invocation: true`, so it runs only when the user invokes it explicitly — which is why a model-driven session never reaches the ADR step on its own.

Because the wrapper delegates everything, `CONTEXT-FORMAT.md` and `ADR-FORMAT.md` live in
`~/.claude/skills/domain-modeling/` — both confirmed present on 2026-08-22 — not in
`grill-with-docs/`. Everything below is therefore an addition to a one-line baseline, not a
correction of it.

## Project additions

### Grill dimensions

**Why:** the wrapper delegates to a general-purpose grilling skill that knows nothing about a
Game Boy's budgets or this project's definition of done.

Beyond the baseline's general stress-testing, every grill in this project must cover:

- **Requirements** — what must be true for this to be done.
- **Acceptance criteria** — concrete, checkable, numbered.
- **Scope boundaries** — what is explicitly *out* of scope, recorded as such.
- **GB hardware constraints** — WRAM, VRAM, OAM, and ROM bank budgets; SM83/SDCC limits. A design that has not been costed against these budgets has not been grilled.

### Explore before asking

**Why:** a grilling skill's instinct is to ask; in this codebase most of what it would ask is
discoverable, and asking wastes the user's turns on facts.

If a **fact** can be found by exploring the codebase or environment, look it up instead of asking. The **decisions** are the user's — put each one to them and wait. For anything spanning more than 2 files or any open-ended search, dispatch the Explore agent rather than accumulating inline reads.

### Paper trail

**Why:** `domain-modeling`'s `ADR-FORMAT.md` prescribes numbered ADR files in a repo directory.
This project keys ADRs off the work item and files them as GitHub issues, which no upstream
skill can know. The `ADR-FORMAT.md` *content structure* is still used verbatim.

- **Glossary / domain context** → `CONTEXT.md` at the repo root — the one design artifact this project keeps as a local file. Glossary only — totally devoid of implementation details. It is not a spec, not a scratchpad, not a decision log. **Written inside the worktree and merged via PR** — never edited directly in the main working tree, never committed straight to `master`.
- **Decisions** → an `adr`-labeled **GitHub issue**, offered sparingly: only when the decision is hard to reverse, surprising without context, AND the result of a genuine trade-off. If any of the three is missing, skip the ADR. Filing procedure:
  - **Key.** An ADR's key is the issue number of the **work item being worked when the decision was taken** — never a counter, and — except in the no-work-item case below — never the ADR issue's own number. The work item is the PRD, bug or chore issue being implemented, never a run log, a review, or another ADR. Title: `ADR <work item#>: <decision title>`.
  - **One ADR per work item.** Before creating one, look for an existing ADR: `gh issue list --label adr --state all --search "ADR <key> in:title"` (`--state all` because an ADR is closed once its work item closes). If it exists, do not file a second: reopen it if closed, append the next `### Dn`, and close it again if it was closed. That search is what keeps one ADR per key.
  - **Body shape.** Each decision is a `### Dn: <title>` section carrying its own `Status: Accepted` or `Status: Superseded by ADR <key> D<n>` line, followed by the baseline `ADR-FORMAT.md` content structure. `Status:` lives on the decision, never on the issue.
  - **Ambiguous keys.** A decision taken under a **child spec** of an epic keys off the child spec, never the epic. A decision with **no work item** makes the ADR its own work item — it is **self-keyed**, its key is its own issue number, and it is the one case needing a retitle after `gh issue create` — file it with the decision title alone, then `gh issue edit <N> --title "ADR <N>: <decision title>"` once GitHub has assigned the number.
  - **Lifecycle.** The issue stays **open** while its work item is open and is closed when the work item closes; a self-keyed ADR closes on acceptance.
  - **Citations.** `[ADR 441](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/467)` in markdown, `(ADR 441)` in code comments; append `Dn` to the link text to cite one decision. The link target is always the ADR's own issue, never the work item whose number is the key. Never a bare second issue number.
  - **Board.** Add it to the "Nuke Raider — Documents" project with `Type = ADR` and
    `Status = Todo`, resolving both fields' ids and their option ids by name — the same
    `gh project field-list` lookup the neighbouring instructions use, since option ids are
    regenerated whenever the option set is edited.
- Use `domain-modeling`'s `CONTEXT-FORMAT.md` for the glossary and its `ADR-FORMAT.md` for the **content structure** of an ADR — the location and numbering prescription (a numbered file in a repo directory) is **overridden** by the filing procedure above: here an ADR is a GitHub issue keyed off its work item, not a numbered file.

### PRDs stay on GitHub

**Why:** same reason as the `brainstorming` overlay's no-local-spec rule — a local PRD file would
be a second source of truth beside the GitHub issue.

The grill's output feeds the `prd` skill, which files a **GitHub issue**. Never write a local PRD file. `CONTEXT.md` is the *only* design artifact that lives in the repo — requirements, feature specs, and decisions do not.

### Tone

**Why:** `docs/game/game-design.md` is the binding tone authority for this game and exists
nowhere upstream.

Feature and copy decisions are grilled against `docs/game/game-design.md` — post-apocalyptic wasteland, sparse dry humor, every word earns its place.
