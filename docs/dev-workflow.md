# Developer Workflow — Nuke Raider

This document is **co-authoritative** with `.claude/skills/`, `.claude/agents/`, and `CLAUDE.md`.
Any PR that touches a skill, agent file, or CLAUDE.md **must also update this document**.

---

## 1. Overview

Nuke Raider is a Game Boy Color game built with GBDK-2020 and SDCC.

- Source: `src/*.c` / `src/*.h`
- Tests: `tests/test_*.c` (gcc + Unity, no hardware)
- Assets: `assets/` → Python tools → `src/` generated C files
- ROM output: `build/nuke-raider.gb`
- Emulator: Emulicious (`java -jar ~/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb`)

Claude Code assistance is provided through **skills** (`.claude/skills/`) and **agents**
(`.claude/agents/`). Skills are invoked with the `Skill` tool; agents with the `Agent` tool.

### Skill overlays

The workflow skills below — brainstorming, writing-plans, executing-plans,
subagent-driven-development, finishing-a-development-branch, dispatching-parallel-agents, and
grill-with-docs — are **not** forked into `.claude/skills/`. They run from their auto-updating
marketplace baselines (superpowers, plus `grill-with-docs` from `mattpocock/skills`), and this
project's deltas live in `.claude/skill-overlays/<name>.md`.

`tools/skill_overlay_hook.py` injects the matching overlay whenever one of those skills is
invoked — via `PostToolUse` on the `Skill` tool for model-invoked skills, and via
`UserPromptSubmit` for user-typed `/commands`, which bypass the Skill tool. Both hooks are
registered in `.claude/settings.json`. On conflict, **the overlay wins** over the baseline.

Each overlay's `baseline:` frontmatter pins the version it was written against. When the
installed superpowers version moves past that pin, the hook prepends a drift warning to the
injected context — re-sync that overlay against the new baseline when it fires. The hook is
fail-open: a missing overlay, malformed input, or any internal error produces no output and
exit 0, so it can never block a session. Shared reference material for the overlays lives in
`.claude/skill-overlays/references/`.

Only skills with **no** upstream baseline (`prd`, `bank-pre-write`, `doc-review`,
`design-an-interface`, `triage-issue`, the asset-pipeline skills, …) remain as real
directories under `.claude/skills/`.

---

## 2. Branch & Worktree Policy

- **Never commit directly to `master`.** All work goes on a feature branch and merges via PR.
- **Always work inside a git worktree.** Every file operation — create, edit, delete — must
  happen in a worktree. Use `EnterWorktree` or the `using-git-worktrees` skill before any write.
- **Integrate via PR only.** Never merge feature branches to master locally.
- Use `gh` for all GitHub operations. Run `gh auth setup-git` if push fails.
- **Settings are tiered.** `~/.claude/settings.json` holds machine values (`GBDK_HOME`, `PYTHONUTF8`, `EMULICIOUS_INI`, `MAKE_PATH_PREPEND`, absolute-path allow rules); `.claude/settings.json` is tracked and holds the curated allowlist, the deny list and all hook wiring; `.claude/settings.local.json` is gitignored scratch and is never committed. New permissions are promoted as generalized wildcard rules into the tracked file, or discarded. Validate with `python tools/allowlist_lint.py`; `make test-tools` enforces it. See `docs/adr/0001-settings-tier-contract.md`.

---

## 3. Outer Dev Loop

```
brainstorming skill
  → /prd skill (creates GitHub issue with PRD)
  → [new session] writing-plans skill (creates docs/plans/YYYY-MM-DD-issue<N>-<slug>.md)
  → subagent-driven-development skill (executes plan, task-by-task)
  → finishing-a-development-branch skill (tests → gates → smoketest → PR)
```

### TDD cycle (for C files)

When executing a plan task that creates or modifies `src/*.c`/`src/*.h`, dispatch the `gbdk-expert` agent with:

> `implement this task: <full task text from plan>`

`gbdk-expert` owns the full cycle:
1. Write failing test → `make test` → FAIL
2. Invoke `bank-pre-write` skill (hard gate)
3. Write minimal implementation → `make test` → PASS
4. `make` → ROM builds
5. Invoke `bank-post-build` skill (hard gate)
6. Run refactor checkpoint: "Does this generalize, or hard-coded for N=1?"
7. Invoke `gb-c-optimizer` agent on new/modified C files — **review AND fix** (applies edits directly, then rebuilds to verify)
8. Commit

**Consultation mode** (API questions, hardware register questions): call `gbdk-expert` agent without the "implement this task:" prefix — it answers as normal.

### Non-C tasks (docs, Python, JSON, assets)

Write → verify → commit. No bank gates required.

---

## 4. Build & Test Gates

### Test runner

```bash
make test                # unit suite — C game logic (gcc + Unity, no GBDK needed), ~170 s
make test-tools          # tool suite — this repo's own Python tooling, ~6 s
```

The tool suite **discovers** every `tests/test_*.py`: adding a test module gates it, with no
`Makefile` edit. Nothing is opted in by name, because a hardcoded list is how two modules went
ungated for four months (#441).

**POSIX-only imports must be guarded.** `curses`, `termios` and `tty` do not exist on Windows.
Import them in a `try/except ImportError` that binds the name to `None`, and check for `None` at
the TUI entry point — see `tools/balancer.py` and `tools/dialog_editor.py`. An unguarded import
takes the whole module out of the suite: the module errors at import, and on a green-looking run
that reads as "not my problem". Both matrix legs of the `Tool Tests` CI job exist to catch this.

### Gates that run without you

Local gates are **repository hooks**, not agent hooks, so they see every actor — any shell, any
tool, any agent, or a human in a plain terminal. They are split by cost. Rationale:
[`docs/adr/0002-local-gates-are-repository-hooks.md`](adr/0002-local-gates-are-repository-hooks.md).

| Hook | Runs | Cost | Blocks |
|------|------|------|--------|
| `.githooks/pre-commit` | tool suite (unittest discovery, direct — not via `make`) | ~6 s | the commit |
| `.githooks/pre-push` | `tools/prepush_build.py` → `make clean && make` | ~29 s | the push |

`.githooks/` is tracked. `make` (and `make test-tools`) depends on a `hooks` target that runs
`python tools/install_hooks.py`, which sets `core.hooksPath` idempotently — so a fresh clone is
gated after one build, with no setup step and no rewrite on later builds. Undo with
`git config --unset core.hooksPath`.

`pre-commit` deliberately does not call `make`: the `Makefile` pins `SHELL := bash` and expects
`GBDK_HOME`, so a commit from a bare `cmd.exe` would die on `make: bash: command not found` for a
reason unrelated to the tests. `tests/test_repo_hooks.py` asserts the hook's command and the
`Makefile` recipe stay byte-identical, since bypassing `make` is exactly what lets them drift.

Anything that shells out to git from inside a hook must scrub `GIT_DIR` and friends first
(`install_hooks.clean_env`) — git exports them into every hook's environment and they override
`cwd`, so an unscrubbed call silently operates on the invoking repository instead of the one you
named.

`--no-verify` bypasses both. That is acceptable: CI is the authority, so a bypassed local hook
costs a round-trip, not correctness.

### Agent hooks: name both shell tools

Hook matchers in `.claude/settings.json` are regex-matched against the **tool name**, so `"Bash"`
never matches `"PowerShell"`. Any matcher naming one shell tool must name both — write
`"Bash|PowerShell"`. Three hooks were registered `Bash`-only and had never fired on a machine
configured to use the PowerShell tool (#441); a gate whose failure mode is total silence is not
left to review. `python tools/allowlist_lint.py --hygiene` fails on a single-shell matcher, and
`make test-tools` runs it.

### CI-enforced gates

CI is the authority. `master` has branch protection with these checks required, **including for
administrators** — the names must match exactly, and a matrix job contributes one check per leg:

| Required check | Job in `.github/workflows/build.yml` |
|----------------|--------------------------------------|
| `Unit Tests` | `test` — `make test` |
| `ROM Build` | `build` — `make` |
| `Tool Tests (ubuntu-latest)` | `test-tools` matrix leg |
| `Tool Tests (windows-latest)` | `test-tools` matrix leg |

Branch protection lives outside the repository, so this table is its only trace. Inspect it with:

```sh
gh api repos/:owner/:repo/branches/master/protection --jq '.required_status_checks.contexts'
```

Never add a `paths:` filter to these jobs — a filtered required check never reports, and the PR
deadlocks waiting for it.

### ROM build

```bash
make
make clean && make   # clean build (required before smoketest)
```

### Bank gates (C files only)

| Gate | When | Skill |
|------|------|-------|
| `bank-pre-write` | Before writing any `src/*.c` or `src/*.h` | `bank-pre-write` skill |
| `bank-post-build` | After successful ROM build, before smoketest | `bank-post-build` skill |

Every `src/*.c` file must have an entry in `bank-manifest.json` before it is written.
`bank_check.py` (a Makefile dependency) enforces this at build time.

### Memory budgets

| Resource | Budget | Notes |
|----------|--------|-------|
| OAM | 40 sprites | Player = 2; rest for enemies/projectiles/HUD |
| VRAM BG tiles | 192 (DMG bank 0) + 192 (CGB bank 1) | CGB bank 1 for color variants |
| WRAM | 8 KB | Large arrays must be `global` or `static`, never local |
| ROM | MBC5, 32 banks (`-Wm-ya32`), up to 512 KB | Code stays in bank 0; assets tagged for banking |

Run `make memory-check` to validate budgets. Any FAIL or ERROR must be fixed before continuing.

### SDCC / GBDK constraints

- No `malloc`/`free` — static allocation only
- No `float`/`double` — use fixed-point integers
- No compound literals — SDCC rejects `(const uint16_t[]){...}`; use named `static const` arrays
- Large local arrays (>~64 bytes) risk stack overflow — use `static` or global
- Prefer `uint8_t` loop counters over `int`
- All VRAM writes must occur during VBlank (after `wait_vbl_done()`)
- Only bank-0 files (no `#pragma bank`) may call `SET_BANK` / `SWITCH_ROM`

### VBlank frame order

```
wait_vbl_done()
  → player_render()        // OAM
  → camera_flush_vram()    // BG tile streams
  → move_bkg(cam_x, cam_y) // scroll registers
  → player_update()        // game logic
  → camera_update()        // buffer new columns/rows
```

### Scalability conventions

- **SoA entity pools** — use Structure-of-Arrays, not Array-of-Structs. One array per field:
  ```c
  static uint8_t enemy_x[MAX_ENEMIES];
  static uint8_t enemy_y[MAX_ENEMIES];
  static uint8_t enemy_active[MAX_ENEMIES];
  ```
  SoA reduces each field access to a direct `base + i` load. Hot loops iterate one field at a
  time — exactly the SoA access pattern. AoS forces stride multiplication (`i * sizeof(Enemy)`)
  before every field access — SDCC cannot eliminate this on the SM83.
- **Fixed-size pools with `active` flag** — no singletons for entities that could multiply.
- **Capacity constants in `src/config.h`** — the single place to tune memory vs. features.
- **Refactor checkpoint before closing any task:** "Does this generalize, or did we hard-code
  something that breaks when N > 1?" If hard-coded and not fixing now → open a follow-up issue.

---

## 5. Debugging Workflow

For **compile errors**: check the GBDK constraints above; invoke `gbdk-expert` agent.

For **runtime issues** (crashes, glitches, wrong values): follow CLAUDE.md's Debugging Rules
(one variable per test; a shifted crash is not the same bug), then dispatch the
`emulicious-debug` agent for interactive instrumentation or `pyboy-debug` for headless
diagnosis. Its GBC-specific diagnostic hints live in the agent file itself.

Key tools in Emulicious:
- **EMU_printf** (`src/debug.h`) — formatted print output visible in the Emulicious console
- **Step-through debugger** — breakpoints, register inspection, memory viewer
- **Tile/sprite viewers** — verify VRAM contents, OAM state, palette assignments
- **Tracer + profiler** — identify hot paths and timing issues

Launch command (from worktree directory):
```bash
java -jar C:\Tools\Emulicious\Emulicious.jar build/nuke-raider.gb
```

### Headless screenshots

`tools/screenshot.py` boots the ROM headlessly via PyBoy and captures a PNG — useful for
diagnosing visual bugs without launching Emulicious interactively.

```bash
python tools/screenshot.py \
  [--steps '[...]']          # JSON navigation sequence
  [--steps-file path.json]   # steps from file (avoids shell-quoting issues)
  [--out build/screenshot.png]  # default output path (worktree-safe)
```

Screenshots land in `build/` (worktree-relative) by default — visible from Windows via
`\\wsl$\Ubuntu\...\build\screenshot.png`.

Invoke the `screenshot` skill before running the script to get the full step API
(advance, press, wait_memory, mid-sequence screenshot).

After capturing, use the `Read` tool on the output path to view the image inline in conversation.

### Headless smoketest

`make smoketest` boots the built ROM under PyBoy and runs every scenario in
`tools/scenarios/`, asserting the game reaches gameplay and stays alive. It is the
blocking VERIFY gate for the agent factory.

- `tools/pyboy_scenario.py` is the shared step engine. `tools/screenshot.py` uses it too, so
  both tools accept the same step vocabulary.
- Scenarios are JSON. A scenario may reuse another by name:
  `{"action": "include", "name": "reach-race"}` — includes are inlined at load time.
- Navigation is derived from `build/game-manifest.json` rather than hardcoded:
  `{"action": "nav", "to": "track", "id": 1}` expands the BFS path the build already computes
  from `assets/maps/overmap.tmx`, so scenarios survive map edits.
- `"blocking": false` marks an evidence scenario — it runs and reports, but never fails the gate.
- Symbols resolve from `build/game-manifest.json` first, then `build/nuke-raider.noi`
  (full names), then `build/nuke-raider.map` (names truncated to 9 characters — last resort).
  `static` variables appear in none of the three and cannot be watched or asserted.
- Every run writes `build/smoketest/<scenario>/`: `results.json` (with a `verdict` field),
  `trace.jsonl` (WRAM sentinels sampled every 30 frames), and checkpoint screenshots.
- Differential debugging: `--ref-rom PATH` re-runs the same scenario against a reference ROM and
  reports the first WRAM divergence by step. If the scenario fails on both ROMs it is reported
  `scenario-invalid` rather than blamed on the game.

Exit codes: `0` pass, `1` run failure, `2` tool or usage error.

Two facts about the game that scenarios must respect:

- **The D-pad is the accelerator**, not `A` (`player.c`: `gas` is gated on
  `J_UP|J_DOWN|J_LEFT|J_RIGHT`); `A` fires. A scenario that "holds A to drive" sits still.
- **"Race is live" is `_hp > 0`**, not `_racer_active`. `hp` is written only by `damage_init()`
  in `state_playing`, so it is 0 through boot and menus. `_racer_active` is `racer_active[0]`,
  the AI-racer pool flag — Track 1 spawns no AI racers, so it stays 0 for a whole valid race.

`make test-tools` covers the engine itself host-side (no ROM, no PyBoy emulation — though it does
import PyBoy via `screenshot.py`). The two gates are deliberately separate: unit tests verify the
engine, `make smoketest` verifies the ROM.

---

## 6. Asset Pipeline

Source art lives in `assets/`; generated C files live in `src/`. Both are checked into git.

```
assets/sprites/<name>.aseprite  →  aseprite --batch  →  assets/sprites/<name>.png
assets/maps/tileset.aseprite    →  aseprite --batch  →  assets/maps/tileset.png
assets/maps/track.tmx           →                    →  (used directly by tmx_to_c.py)
         │                               │                        │
         ▼                               ▼                        ▼
png_to_tiles.py             png_to_tiles.py               tmx_to_c.py
         │                               │                        │
         ▼                               ▼                        ▼
src/<name>_sprite.c         src/track_tiles.c          src/track_map.c
```

```bash
make export-sprites   # re-export all .aseprite → .png (requires aseprite in PATH)
make                  # regenerate all .c files if sources are newer, then build ROM
```

> **Multi-frame sprites:** `--save-as` produces numbered files (`name1.png`, `name2.png`) for
> multi-frame sprites — not a sheet. Use `--sheet --sheet-type horizontal` and add a specific
> Makefile override rule. See the `sprite-expert` agent for the full pattern.

See `docs/asset-pipeline.md` for the full pipeline including palette setup, tile encoding,
and Aseprite authoring conventions.

For Aseprite CLI details (flags, batch mode, layer/tag filtering), invoke the `aseprite` skill
**before** running any `aseprite` command.

---

## 7. PR Checklist

Before pushing and creating a PR, verify all of the following:

- [ ] `make test` passes (zero failures)
- [ ] `make test-tools` passes (tool suite — also enforced by the `pre-commit` repository hook)
- [ ] `bank-post-build` skill passes (no FAIL banks)
- [ ] `make memory-check` passes (no FAIL/ERROR budgets)
- [ ] Smoketest in Emulicious confirmed by user
- [ ] `git fetch origin && git merge origin/master` merged from latest master
- [ ] Clean build (`make clean && make`) succeeds
- [ ] **If user-visible behavior changed:** README module table updated
- [ ] **If any `.claude/skills/`, `.claude/agents/`, or `CLAUDE.md` file changed:** this file (`docs/dev-workflow.md`) updated
- [ ] PR body includes `Closes #N` for the related issue
- [ ] `python tools/trace.py --check` passes (no ERROR lines; legacy warnings are expected)
- [ ] Any new tool permission promoted into `.claude/settings.json` as a generalized rule (never `.claude/settings.local.json`, which is gitignored)

Use `gh pr create` with a `## Summary` + `## Test Plan` body. After merge, verify the linked
issue is auto-closed; if not, run `gh issue close N`.

---

## 8. Traceability

Every change is traceable end to end: **issue → plan → branch → PR → merge**.

### Conventions

| Link | Convention | Enforced by |
|------|-----------|-------------|
| issue → plan | Plan filename `docs/plans/YYYY-MM-DD-issue<N>-<slug>.md` **and** an `**Issue:** #N` line in the plan header | `.claude/skill-overlays/writing-plans.md` (self-review check #6), `tools/trace.py --check` |
| plan → branch | Worktree branch name ends in `-<N>` (e.g. `worktree-plan-laser-weapon-damage-424`) | convention; `trace.py` uses it only when no PR exists yet |
| branch → PR | PR body contains `Closes #N` | `finishing-a-development-branch` skill, `.github/workflows/pr-linked-issue.yml` |
| PR → merge | GitHub auto-closes the issue on merge | GitHub |

### Tracing one issue

```sh
python tools/trace.py 424           # human-readable chain
python tools/trace.py 424 --json    # machine-readable
```

Renders issue title/state, the plan file (searching the working tree first, then git history
for plans deleted after merge), branch, PR and merge commit. Any link that cannot be resolved
prints `(not found)` rather than failing.

### Checking the whole repo

```sh
python tools/trace.py --check                # plans + PRs (needs gh)
python tools/trace.py --check --plans-only   # plans only, offline
```

Exit `0` = pass (warnings allowed), `1` = violations, `2` = operational error.

`ADOPTION_DATE` in `tools/trace.py` is the single knob governing severity: plans and PRs dated
on or after it are **errors**; older ones are **warnings**. Back-filling historical plans is
deliberately out of scope — the warnings are expected and are not a to-do list.

### CI

`.github/workflows/pr-linked-issue.yml` runs on every PR open/edit/reopen/sync and fails when
the PR body has no `Closes`/`Fixes`/`Resolves #N` reference. It is advisory: the check is not
in branch protection, so it does not block merge. Its regex is a bash mirror of `CLOSES_RE` in
`tools/trace.py` — change both together.

The gate-enforcing workflows are separate: `.github/workflows/build.yml` provides the four
required status checks listed in §4, "CI-enforced gates". Those *do* block merge.
