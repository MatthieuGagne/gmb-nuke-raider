# CLAUDE.md

## Build & Run

Output ROM: `build/nuke-raider.gb`.

**Two ROMs:** `make` builds the release ROM; `make build-debug` builds the debug ROM, which adds
`DBG_STATIC` symbols, the bank-30 test command mailbox and a stack reserved to 0xDF00. The two
ROMs differ **by design** in every bank, bank 0 included — do not treat a byte difference as a
defect. What parity actually requires is defined by `tests/test_rom_parity.py`; read it before
changing anything about the debug build.

C coding rules, entity pools, memory budgets, the state machine table and the ROM header live in
[`src/CLAUDE.md`](src/CLAUDE.md) (loads automatically when editing `src/`), with full rationale in
`docs/dev-workflow.md` §4.

## Game Design & Influences

Full design doc: [`docs/game/game-design.md`](docs/game/game-design.md) — consult before making
feature, tone, or UX decisions.

**Tone:** Post-apocalyptic wasteland (*Road Warrior*). Sparse, dry humor. Judas Priest energy —
every word earns its place.

## Git & GitHub

Always use `gh` for git push/pull and GitHub operations. Run `gh auth setup-git` if push fails due to missing credentials.

**Settings tiers:** machine (`~/.claude/settings.json`) holds `env` and any absolute path; repo
(`.claude/settings.json`, tracked) holds the allowlist, deny list and agent hook wiring —
repository hooks live in `.githooks/`; scratch (`.claude/settings.local.json`, gitignored) is
never committed. A matcher naming one shell tool must name both (`Bash|PowerShell`). A session
approval is either rewritten as a generalized rule in the tracked repo file or discarded — never
copied in verbatim. Validated by `python tools/allowlist_lint.py`; rationale in
[ADR 441](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/467) and
[ADR 443](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/466).

**Always create a PR after pushing a branch** — no need to ask. **Every PR must reference an
issue**, or the `PR Linked Issue` CI check fails and blocks the merge; if no issue exists, file one
first. Include `Closes #N` in the PR body to auto-close it on merge, and never write
`close`/`fix`/`resolve` next to a `#N` you do not intend to close — GitHub's parser ignores
negation. When a PR is merged, verify the linked issue is closed; if not, `gh issue close N`.

## Skills & Agents

Agents live in `.claude/agents/`, skills in `.claude/skills/` — each file's frontmatter
(`description` / when-to-use) is the authoritative trigger and is surfaced automatically; don't
duplicate those descriptions here. `docs/dev-workflow.md` is co-authoritative and maps each one
to its workflow step.

Two things not obvious from frontmatter alone:
- The superpowers workflow skills (brainstorming, writing-plans, executing-plans,
  subagent-driven-development, finishing-a-development-branch, dispatching-parallel-agents)
  run from their auto-updating baselines; project deltas live in
  `.claude/skill-overlays/<name>.md` and are injected automatically by
  `tools/skill_overlay_hook.py` (PostToolUse on Skill + UserPromptSubmit hooks in
  `.claude/settings.json`). On conflict, the overlay wins. Each overlay's `baseline:`
  frontmatter pins the superpowers version it was written against; the hook warns when
  the installed version has moved (re-sync the overlay when it fires). `grill-with-docs` also
  has an overlay, but its baseline is a local skill pinned by date, which the hook cannot
  version-check.
- `grill-with-docs` carries `disable-model-invocation: true`, so a model-driven session can never
  reach it. When a decision needs an ADR, ask the user to run it.
- `factory` (`.claude/skills/factory/`) is the unattended orchestrator. It is invoked
  explicitly as `/factory <issue#>` and never fires automatically. It writes run state only
  through `tools/factory_event.py` and publishes to GitHub only through
  `tools/factory_publish.py` — never directly.

### Pi harness

Running under the Pi agent (`pi`) instead of Claude Code? Two gates are absent there: **skill
overlays never inject** (read `.claude/skill-overlays/` yourself) and **the `pwsh-*` background-job
tools bypass every hook** (#572) — run builds and pushes through the shell tool, not a job.
Full setup, the remaining missing gates, and why the two harnesses' hook anchors must not be
copied between files: [`docs/pi-harness.md`](docs/pi-harness.md) — read it when running under Pi.

## Debugging Rules

- **Worktree CWD**: Before every `make` or emulator launch, verify the current directory is the correct worktree directory (`pwd`). After any worktree cleanup, `cd` to a valid directory before running further commands.

## Workflow

This project uses [Superpowers](https://github.com/obra/superpowers), installed as a marketplace
plugin.

**Outer loop:** brainstorming → PRD (`/prd`) → [separate session] writing-plans → subagent-driven-development

**Factory loop (unattended):** `/factory <issue#>` drives a lint-passing PRD issue through
GATE → PLAN → BUILD → VERIFY → SHIP with no interactive input, ending at a reviewable PR.
Flags: `--stage <NAME>`, `--resume`, `--dry-run`. Run state lives in `.factory/runs/issue-<N>/`
at the **main** repo root, so any session locates a run from the issue number alone
(`python tools/factory_status.py`). The factory never merges, never commits to `master`, never
force-pushes, never passes `--no-verify`, and never deletes a worktree or branch. Full contract:
`.claude/skills/factory/SKILL.md` and its `references/stages.md`.

**GitHub issue links:** When the user pastes a GitHub issue URL (e.g. `https://github.com/.../issues/N`), first fetch the issue and check its **Files Impacted** or **Out of Scope** sections. If ALL touched files qualify as doc-only (`.md`, `.txt`, `.json` except `bank-manifest.json`, files under `.claude/skills/` or `.claude/agents/`), invoke the `doc-review` skill. Otherwise invoke `writing-plans`. Do not ask for confirmation.
**TDD red/green command:** `make test` (gcc + Unity, no hardware needed — use `/test` skill). **Early-exit behavior:** the Makefile uses `|| exit 1` — it stops at the first failing test binary (alphabetical order). Test binaries after the first failure do NOT run. Fix all failures starting from the earliest binary; re-run `make test` after each fix to reveal the next hidden failure.
**Bank manifest maintenance:** Every new `src/*.c` file must have an entry in `bank-manifest.json` before it is written. `bank-pre-write` hook (`tools/bank_check_hook.py`) and `tools/bank_check.py` (Makefile dependency) both enforce this. Every banking-related PR must update ALL artifacts: `bank-manifest.json`, the `bank-pre-write` and `post-build-gates` skills, `tools/bank_check.py`, the `gbdk-expert` agent, and this file.
**Build verification:** `make` (use `/build` skill)
**Map source of truth:** `assets/maps/track.tmx` (and `assets/maps/overmap.tmx`) are the authoritative sources for all map tile data. Never patch tile values directly into generated files (`src/track_map.c`, `src/overmap_map.c`). If a tile must be placed (e.g. `TILE_BOOST`), add it to the TMX in Tiled, then re-run `make clean && make` to regenerate. Hand-edits to generated files are silently overwritten on the next build.

**PRDs, ADRs & the document board:** GitHub issues only — no local files; `CONTEXT.md` is the sole
in-repo exception. Routing, sub-issue wiring, the ADR key/lifecycle/citation rules, the `Type`
table and the `Idea` swimlane: [`docs/document-conventions.md`](docs/document-conventions.md) —
read it before filing, typing or wiring any document issue. The `/prd` skill loads it for you.

**Worktree policy:** ALL file operations — creating, editing, or deleting files — MUST happen inside a git worktree. This applies to implementation plans, code, tests, docs, and any other file. Before touching any file, use the `using-git-worktrees` skill or `EnterWorktree` tool to enter a worktree. Never write, edit, or delete files directly in the main working tree. If you are not currently in a worktree, STOP and enter one first. **`make test` must also be run from the worktree directory** — running it from the main repo root tests stale compiled binaries and silently masks real failures in the worktree.

**Smoketest gate:** NEVER push or create a PR before running a smoketest in the emulator. Always push AFTER the smoketest passes.
1. Fetch and merge latest master: `git fetch origin && git merge origin/master` (from the worktree directory). NEVER use `git merge master` alone — the local master ref may be stale.
2. Always do a clean build: `make clean && make`. Never assume a prior build is still valid — this
   matters most when testing historical PRs or comparing versions.
3. `make memory-check` fires automatically via PostToolUse hook after step 2 — check the hook output; if any budget is FAIL or ERROR, stop and fix before continuing.
4. Ask the user for confirmation before launching the ROM. If they confirm, launch in the background from the worktree directory (NEVER from the main repo's `build/` — it may be stale), using the emulator launch command in `CLAUDE.local.md`.
5. Ask them to confirm it looks correct before proceeding.
6. Only after the user confirms: update `README.md` if the feature adds or changes any
   user-visible behavior, then push the branch and create the PR. The `pre-push` repository hook
   runs `make clean && make` and blocks the push if it fails — steps 2–3 are still yours to run,
   the hook only guarantees the tree you publish builds.

The `factory` skill defines the one exception to steps 4-5, for unattended runs only.

**GB skill gates:**
- Before writing any `src/*.c` or `src/*.h` file → `bank-pre-write` fires **automatically** via PreToolUse hook; invoke the `gbdk-expert` agent (its frontmatter defines consultation vs implementation mode)
- After a successful build → the post-build gate (bank check + `make memory-check`) fires **automatically** via PostToolUse hook; no manual invocation needed
- When debugging any runtime issue → invoke the `emulicious-debug` agent (interactive, needs a GUI) or `pyboy-debug` (headless/unattended — required under `NUKE_FACTORY_RUN`, where no GUI or human gate exists)

**Branch policy:** NEVER commit directly to `master`. All work goes on a feature branch and merges via PR.

**Doc-only workflow:** When ALL files changed in a session are non-compiled doc files, an
abbreviated path replaces the full gate sequence. The `doc-review` skill defines it and is the
entry point for doc-only PRD implementations, in place of `writing-plans` + `executing-plans`.
*Conservative rule:* if ANY `.c` or `.h` file is touched in the same session, the **full workflow
applies** — no exceptions.
