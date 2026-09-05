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

Always use `gh` for git push/pull and GitHub operations.

**Settings tiers:** machine (`~/.claude/settings.json`) / repo (`.claude/settings.json`, tracked)
/ scratch (`.claude/settings.local.json`, gitignored, never committed). A session approval is
either rewritten as a generalized rule in the tracked repo file or discarded — never copied in
verbatim. Validated by `python tools/allowlist_lint.py`; rationale in
[ADR 441](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/467) and
[ADR 443](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/466).

**Always create a PR after pushing a branch** — no need to ask. **Every PR must reference an
issue**, or the `PR Linked Issue` CI check fails and blocks the merge; if no issue exists, file one
first. Include `Closes #N` in the PR body to auto-close it on merge, and never write
`close`/`fix`/`resolve` next to a `#N` you do not intend to close — GitHub's parser ignores
negation. When a PR is merged, verify the linked issue is closed; if not, `gh issue close N`.

## Skills & Agents

Agents live in `.claude/agents/`, skills in `.claude/skills/`; overlay, factory and
reachability mechanics are in the import below.

@docs/skill-wiring.md

### Pi harness

Running under Pi instead of Claude Code? **The `pwsh-*` background-job tools bypass every
hook** (#572) — run builds and pushes through the shell tool, not a job. Read
[`docs/pi-harness.md`](docs/pi-harness.md) for the rest.

### omp harness

Running under omp (the oh-my-pi fork of Pi)? **`tools.approvalMode` defaults to `yolo`** —
weaker than either other harness. Read [`docs/omp-harness.md`](docs/omp-harness.md) for the rest.

## Debugging Rules

- **Worktree CWD**: Before every `make` or emulator launch, verify the current directory is the correct worktree directory (`pwd`). After any worktree cleanup, `cd` to a valid directory before running further commands.

## Workflow

**Outer loop:** brainstorming → PRD (the `prd` skill) → [separate session] writing-plans → subagent-driven-development

**Factory loop (unattended):** the `factory` skill, invoked explicitly with an issue number,
drives a lint-passing PRD issue through
GATE → PLAN → BUILD → VERIFY → SHIP with no interactive input, ending at a reviewable PR.
Flags: `--stage <NAME>`, `--resume`, `--dry-run`. Run state lives in `.factory/runs/issue-<N>/`
at the **main** repo root, so any session locates a run from the issue number alone
(`python tools/factory_status.py`). The factory never merges, never commits to `master`, never
force-pushes, never passes `--no-verify`, and never deletes a worktree or branch. Full contract:
`.claude/skills/factory/SKILL.md` and its `references/stages.md`.

**GitHub issue links:** When the user pastes a GitHub issue URL (e.g. `https://github.com/.../issues/N`), first fetch the issue and check its **Files Impacted** or **Out of Scope** sections. If ALL touched files qualify as doc-only (`.md`, `.txt`, `.json` except `bank-manifest.json`, files under `.claude/skills/` or `.claude/agents/`), invoke the `doc-review` skill. Otherwise invoke `writing-plans`. Do not ask for confirmation.
**TDD red/green command:** `make test` (gcc + Unity, no hardware needed — use the `test` skill).

**PRDs, ADRs & the document board:** GitHub issues only — no local files; `CONTEXT.md` is the sole
in-repo exception. Routing, sub-issue wiring, the ADR key/lifecycle/citation rules, the `Type`
table and the `Idea` swimlane: [`docs/document-conventions.md`](docs/document-conventions.md) —
read it before filing, typing or wiring any document issue. The `prd` skill loads it for you.

**Worktree policy:** ALL file operations — creating, editing, or deleting files — MUST happen inside a git worktree. This applies to implementation plans, code, tests, docs, and any other file. Before touching any file, create the worktree through Orca: invoke the `orca-cli` skill (exact commands come from `ORCA skills get orca-cli` — never guess flags). Orca worktrees live under `~\orca\workspaces\<repo>\<name>`. Never use `git worktree add`, the `EnterWorktree` tool, or `.worktrees/`/`.claude/worktrees/` directories. Never write, edit, or delete files directly in the main working tree. If you are not currently in a worktree (check: `git rev-parse --git-dir` differs from `git rev-parse --git-common-dir`), STOP and enter one first. **`make test` must also be run from the worktree directory** — running it from the main repo root tests stale compiled binaries and silently masks real failures in the worktree.

**Smoketest gate:** NEVER push or create a PR before running a smoketest in the emulator. Always push AFTER the smoketest passes.
1. Fetch and merge latest master: `git fetch origin && git merge origin/master` (from the worktree directory). NEVER use `git merge master` alone — the local master ref may be stale.
2. Always do a clean build: `make clean && make`. Never assume a prior build is still valid — this
   matters most when testing historical PRs or comparing versions.
3. `make memory-check` fires automatically after step 2 — check the gate output; if any budget is FAIL or ERROR, stop and fix before continuing. If your harness reports no such output, run `make memory-check` yourself.
4. Ask the user for confirmation before launching the ROM. If they confirm, launch in the background from the worktree directory (NEVER from the main repo's `build/` — it may be stale), using the emulator launch command in `CLAUDE.local.md`.
5. Ask them to confirm it looks correct before proceeding.
6. Only after the user confirms: update `README.md` if the feature adds or changes any
   user-visible behavior, then push the branch and create the PR. The `pre-push` repository hook
   runs `make clean && make` and blocks the push if it fails — steps 2–3 are still yours to run,
   the hook only guarantees the tree you publish builds.

The `factory` skill defines the one exception to steps 4-5, for unattended runs only.

**GB skill gates:**
- Before writing any `src/*.c` or `src/*.h` file → the `bank-pre-write` gate fires **automatically**; dispatch the `gbdk-expert` agent (its frontmatter defines consultation vs implementation mode)
- After a successful build → the post-build gate (bank check + `make memory-check`) fires **automatically**; no manual invocation needed
- When debugging any runtime issue → dispatch the `emulicious-debug` agent (interactive, needs a GUI) or `pyboy-debug` (headless/unattended — required under `NUKE_FACTORY_RUN`, where no GUI or human gate exists)

**Branch policy:** NEVER commit directly to `master`. All work goes on a feature branch and merges via PR.

**Doc-only workflow:** When ALL files changed in a session are non-compiled doc files, an
abbreviated path replaces the full gate sequence. The `doc-review` skill defines it and is the
entry point for doc-only PRD implementations, in place of `writing-plans` + `executing-plans`.
*Conservative rule:* if ANY `.c` or `.h` file is touched in the same session, the **full workflow
applies** — no exceptions.
