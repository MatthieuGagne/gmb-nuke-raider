---
name: brainstorming
baseline: superpowers@6.2.0
---

Project (Nuke Raider) additions and overrides for the baseline brainstorming skill. On conflict, this overlay wins.

## Overrides (do NOT follow the baseline here)

- **No design document is written.** Where the baseline says to save a spec or design doc (e.g. under `docs/superpowers/specs/`), skip it entirely. This project's design artifacts are **PRDs as GitHub issues only** — no local design files. A brainstorm's output is the Resolved / Unresolved / Deferred summary and nothing else.
- **Brainstorming ends at that summary.** Do NOT auto-invoke `writing-plans` (or any planning skill) as a terminal state. The project outer loop inserts `/prd` and a separate planning session between brainstorm and plan. The user invokes the next step when they are ready.
- **Never offer the visual companion.** Its server scripts are bash-only and unsupported on this Windows setup. Skip every baseline instruction to offer, open, or use it — including the just-in-time offer.
- **Grilling uses `grill-with-docs`, not `grill-me`.** `grill-me` no longer exists in this project. Wherever the baseline (or habit) calls for stress-testing the design, invoke the `grill-with-docs` skill. It must not re-invoke brainstorming — continue only once its summary is produced.
- **Design gaps found during self-review are raised as questions to the user — never silently fixed in the spec.** If your own review of the design surfaces a gap, ambiguity, or contradiction, put it to the user as an open question. Quietly patching it hides a decision the user needed to make.

## Project additions

- **Consult the game design doc before any tone, feature, or UX decision:** `docs/game/game-design.md`. Wasteland tone rules (post-apocalyptic *Road Warrior*, sparse dry humor, every word earns its place) are binding on all proposed copy and features.
- **Design-It-Twice is required for any new `src/*.c` module interface.** Invoke the `design-an-interface` skill (`Skill` tool, `skill: "design-an-interface"`) to spawn 4 parallel sub-agents, each constrained to a different lens (minimal API, testability, caller ergonomics, GB efficiency). Compare the results, choose the best, and document why.
- **GB hardware constraints are a standing brainstorm dimension.** Work through this checklist explicitly for any GBC feature before finalizing the design:

| Constraint | Question to answer |
|------------|-------------------|
| **Banking** | Which ROM bank does this code live in? Does it call code in other banks? Are SET_BANK calls safe? |
| **OAM** | How many OAM sprite slots does this use? Running total vs. budget of 40? |
| **WRAM** | How many bytes of WRAM does this use? Are all large arrays global/static (not local)? |
| **VRAM** | How many tiles does this consume? Running total vs. budget of 192 (bank 0) + 192 (bank 1)? |
| **SoA** | Are entity pools Structure-of-Arrays (not Array-of-Structs)? |
| **SDCC** | Any compound literals, float, malloc, large locals, or non-uint8_t loop counters? |
| **Testability** | Which logic can be host-side tested with `make test` (no hardware)? |

- **Resolved / Unresolved / Deferred summary** is the deliverable. Output a short bullet list per category:
  - **Resolved:** decisions that are settled
  - **Unresolved:** open questions that must be answered before implementation begins
  - **Deferred:** items deliberately set aside (not blocking now)

  If Unresolved is non-empty, stop and resolve those questions before continuing.
- **When the user is ready for a PRD**, it goes through the `prd` skill as a GitHub issue and stays at the requirements and design level — no implementation details, code snippets, or file-level task breakdowns (CLAUDE.md "PRD vs Implementation Plan").
- **One question per message.** If a topic needs more exploration, break it into multiple questions rather than stacking them.
