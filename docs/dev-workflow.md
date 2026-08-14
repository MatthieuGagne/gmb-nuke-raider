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

**"The overlay wins" is conditional, and the pin does not enforce it** (#527). The canary
compares *versions*, never *content*, so an overlay that still matches its pin can contradict
that pin's text with no warning — which is how a local file came to revert several upstream
improvements silently. Two rules close that gap:

- **Every surviving override states what the baseline cannot know**, on a `**Why:**` line
  directly under the section (or under the bullet, in overlays that use bullets). Platform
  facts, project-specific agent routing, and repo policy qualify. "The baseline used to work
  differently" does not — an override that cannot state a reason is removed, not kept.
- **Every overlay records a `**Baseline audit:**` line** naming the baseline whose *content* it
  was last read against, and the date. Re-run that audit when the drift warning fires, and when
  an overlay is edited for any other reason.

Only skills with **no** upstream baseline (`prd`, `bank-pre-write`, `doc-review`,
`design-an-interface`, `triage-issue`, `factory`, the asset-pipeline skills, …) remain as real
directories under `.claude/skills/`.

`factory` is the one that carries a `references/` subdirectory of its own
(`.claude/skills/factory/references/stages.md`) — the overlays' shared references live under
`.claude/skill-overlays/references/` and are a separate tree.

One overlay section is a charter rather than a workflow rule: **the adversarial charter for the
final whole-branch review** (`.claude/skill-overlays/subagent-driven-development.md`). The
baseline dispatches that review by prompt-file path rather than by invoking a skill, so an
overlay written against `requesting-code-review` would never be injected — the charter lives in
the overlay of the skill that performs the dispatch, and therefore reaches factory runs and
manual sessions alike (#533).

---

## 2. Branch & Worktree Policy

- **Never commit directly to `master`.** All work goes on a feature branch and merges via PR.
- **Always work inside a git worktree.** Every file operation — create, edit, delete — must
  happen in a worktree. Use `EnterWorktree` or the `using-git-worktrees` skill before any write.
- **Integrate via PR only.** Never merge feature branches to master locally.
- Use `gh` for all GitHub operations. Run `gh auth setup-git` if push fails.
- **Settings are tiered.** `~/.claude/settings.json` holds machine values (`GBDK_HOME`, `PYTHONUTF8`, `EMULICIOUS_INI`, `MAKE_PATH_PREPEND`, absolute-path allow rules); `.claude/settings.json` is tracked and holds the curated allowlist, the deny list and all hook wiring; `.claude/settings.local.json` is gitignored scratch and is never committed. New permissions are promoted as generalized wildcard rules into the tracked file, or discarded. Validate with `python tools/allowlist_lint.py`; `make test-tools` enforces it. See [ADR 443](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/466).

---

## 3. Outer Dev Loop

```
brainstorming skill
  → /prd skill (creates GitHub issue with PRD)
  → [new session] writing-plans skill (creates docs/plans/YYYY-MM-DD-issue<N>-<slug>.md)
  → subagent-driven-development skill (executes plan, task-by-task)
  → finishing-a-development-branch skill (tests → gates → smoketest → PR)
```

### Document issues: label at creation, index at creation

`/prd` creates the issue with `--label prd`, then adds it to the "Nuke Raider — Documents"
project (number `3`, owner `MatthieuGagne`, id `PVT_kwHOAv4a5M4BepB5`) and sets `Type = PRD` and
`Status = Todo` — `gh issue create --label prd` → `gh project item-add` → `gh project field-list`
→ `gh project item-edit` (Type) → `gh project item-edit` (Status): four commands after issue
creation. Resolve every field id and option id by name at runtime; option ids change when the
option set is edited. `tools/factory_publish.py` writes the same two board fields for
`log`-labeled run issues, but not the identical sequence: it sets `Type = Log` once and re-issues
`Status` writes across the run's lifecycle (`In Progress` at start, `Done` at terminal) rather
than setting both once at creation.

`Type` records **kind only**:

| Title prefix | Type |
|---|---|
| `feat:` carrying the `epic` label | Epic |
| `feat:` | PRD |
| `fix:` / `bug:` | Bug |
| `docs:` / `chore:` / `refactor:` / `test:` | Chore |
| `ADR <work item#>:` | ADR |
| `run …` | Log |
| `review:` | Review |

The `Epic` row is first and is matched by **label, not prefix**: an epic is `feat:`-titled like
any other PRD. A master issue owning a set of child specs (#432) carries `epic` in addition to
`prd`, and is typed `Epic`. It is the one type assigned by hand — `/prd` never sets it. Do not
remove `Epic` from the field.

There is no `Follow-up` type — provenance belongs in the issue body. `prd`, `adr`, `log` and
`epic` are the document labels; `Bug` and `Chore` are board types with no matching label.

### Architecture decisions: keyed by their work item

An ADR is an `adr`-labeled GitHub issue whose **key is the issue number of the work item that
was being worked when the decision was taken** — not an allocated counter, and — except in the
no-work-item case below — not the ADR issue's own number. The work item is the PRD, bug or chore
issue being implemented, never a run log, a review, or another ADR. The title is
`ADR <work item#>: <decision title>`. GitHub allocated that number when the work item was filed,
so no counter is read before writing.

**One ADR per work item.** Several decisions taken on the same work item share one ADR issue and
appear in its body as `### D1: …`, `### D2: …`. Before filing a second, search issue titles for
`ADR <key>`, closed issues included; if one exists, append the next `Dn` instead. Cite an
individual decision as `ADR 441 D2`.

**The two ambiguous cases.** A decision taken while working a **child spec** under an epic keys
off the child spec, never the epic. A decision with **no work item** makes the ADR its own work
item, so its key is its own issue number — the ADR is **self-keyed**, and it is the one case
that needs a retitle after `gh issue create`. They cannot collide, because two GitHub issues
cannot share a number.

**Lifecycle.** The ADR issue stays open while its work item is open and is closed when the work
item closes — replacing the older "closed on acceptance" rule, which now survives only for a
self-keyed ADR. A decision taken later, against an already-closed work item, is added by
reopening the ADR, appending the next `Dn`, and closing it again.

**Status is per decision**, not per issue: each `### Dn` carries `Status: Accepted` or
`Status: Superseded by ADR <key> D<n>`.

**Citation form.** `[ADR 441](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/467)` in
markdown, `(ADR 441)` in code comments; append `Dn` to the link text to cite one decision. The
link target is always the ADR's own issue, never the work item whose number is the key. Never a
bare second issue number, and never both the work item and the ADR — the key already names the
work item.

A multi-decision body:

```markdown
### D1: Local gates are repository hooks, not agent hooks
Status: Accepted

Context / Decision / Consequences, per the baseline `ADR-FORMAT.md`.

### D2: The tool suite runs on commit, the clean build on push
Status: Superseded by ADR <key> D<n>

…
```

The `Status:` line is shown with metavariables on purpose: every concrete key in this repo names
a real ADR, and an example that supersedes one of them reads as a fact rather than a form.

Seven ADRs predate this scheme (issues #466–#470, #475 and #490). Each takes its work-item key
as its title and keeps an alias line in its body naming the number it previously carried, so
citations in already-merged PR bodies and closed issues stay resolvable. Nothing parses ADR
keys — there is no validator and no lint rule, by design.

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
make test                # unit suite — C game logic (gcc + Unity, no GBDK needed)
make test-tools          # tool suite — this repo's own Python tooling
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
[ADR 441](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/467).

| Hook | Runs | Cost | Blocks |
|------|------|------|--------|
| `.githooks/pre-commit` | tool suite (unittest discovery, direct — not via `make`) | the whole tool suite — grows with the test count | the commit |
| `.githooks/pre-push` | `tools/prepush_build.py` → `make clean && make` | one clean ROM build | the push |

Neither cost is quoted as a duration: both drift, and a stale figure in a table is worse than no
figure — measure `make test-tools` and `make clean && make` when you need real numbers. Do not
assume the commit gate is the cheaper of the two just because it runs on the more frequent
action; that was true when the split was designed and is worth re-measuring before you rely on it.

`.githooks/` is tracked. `make` (and `make test-tools`) depends on a `hooks` target that runs
`python tools/install_hooks.py`, which sets `core.hooksPath` idempotently — so a fresh clone is
gated after one build, with no setup step and no rewrite on later builds. Undo with
`git config --unset core.hooksPath`.

`pre-commit` deliberately does not call `make`: the `Makefile` pins `SHELL := bash` and expects
`GBDK_HOME`, so a commit from a bare `cmd.exe` would die on `make: bash: command not found` for a
reason unrelated to the tests. `tests/test_repo_hooks.py` asserts the hook's command and the
`Makefile` recipe stay byte-identical, since bypassing `make` is exactly what lets them drift.

**Anything that shells out to git must scrub `GIT_DIR` and friends first** — git exports them
into every hook's environment and they override `cwd`, so an unscrubbed call silently operates on
the invoking repository instead of the one you named. Both hooks `unset` them before running
anything, and `install_hooks.clean_env()` is the one definition for Python callers; use it in
tools *and* in tests.

Any gate intended to catch a human has to be proven from a real terminal, not only from agent tools — agent tools share one environment and therefore share one blind spot. This rule originates from [#441 AC5](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/441): the environment-dependent test shape, where a check passes when run directly and fails under the hook it was written for.

`.claude/settings.json` hook registrations do not hot-reload, so renaming or deleting a hook script breaks every later tool call matching that matcher for the rest of the session. The workaround is to use the other shell tool (Bash ↔ PowerShell), or start a new session. This hazard was observed in [#460](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/460): `git mv tools/precommit_build_hook.py tools/prepush_build.py` made every subsequent Bash tool call fail because the running session still held the old registration.

This is not theoretical. The tool suite runs inside `pre-commit`, and `tests/test_factory_run.py`
builds a scratch repo with `git init` / `git add` / `git commit`. Unscrubbed, those calls ran
against the real repository using the very index being committed — producing a merge commit
titled `init` containing a test fixture file, resetting `core.hooksPath` so the gate stopped
firing, and rewriting `user.email`. `tests/test_repo_hooks.py` now parses every test module with
`ast` and fails any `subprocess.run(['git', …], cwd=…)` that passes no `env=`.

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

### Two ROMs

`make` builds `build/nuke-raider.gb`. `make build-debug` builds `build/debug/nuke-raider.gb`
with its own `.map`, `.noi` and `game-manifest.json`. Neither writes over the other, and
`make clean` removes both. `make memory-check` reports on the release ROM, `make
memory-check-debug` on the debug one.

The two ROMs no longer hold the same bytes (#590 ends #588 AC2). Bank 0 differs: the debug
build reserves the stack at `-Wl-g.STACK=0xDF00` and adds the `BANKED` trampolines the
mailbox's cross-bank calls need, and both live in bank 0. Banks 1-3 differ too, but only in
each `BANKED` call site's absolute operand: a new trampoline shifts every bank-0 address after
it, and banked code calls bank-0 routines by absolute address, so those calls' operands move
with it — the instructions themselves, opcode included, are untouched. Bank 30 exists only in
the debug ROM (the mailbox itself, see below); the release ROM's bank 30 is uniform filler.

`tests/test_rom_parity.py` no longer compares bytes. For banks 1-3 it asserts: every differing
byte belongs to a 16-bit absolute operand whose opcode is unchanged in both ROMs and whose
value is a bank-0 address on both sides; the release-to-debug address mapping is a consistent
function (one release address never maps to two different debug addresses); the number of
distinct relocated targets stays under a cap (128); and the number of distinct relocation
deltas stays under a cap (8). Measured today: 40 distinct targets, 3 distinct deltas, zero
unexplained bytes. It also asserts bank 0 differs (a control — if it didn't, the invariant
above would prove nothing) and that bank 30 is uniform filler in the release ROM and not in the
debug ROM. `DEBUG=1` changes linkage and adds this reserved stack and the mailbox; it does not
otherwise change what the game does.

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
| ROM | MBC5, 512 KB = 32 banks, auto-sized by makebin (`-yo A`) and recorded in cartridge header `0x148` | `-autobank` places code past bank 0, into the autobank pool (banks 1-29) — state code sits in banks 2-3 today; assets tagged for banking. Two banks are pinned by hand instead of autobanked: 31 for `src/music_data.c`, 30 for `src/debug.c` (the debug-ROM-only test command mailbox, #590). `-Wm-ya32` in `CFLAGS` is **not** the ROM bank count: `-ya` is makebin's *RAM* bank count and the value is discarded (header `0x149=0x00`) |

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
- **EMU_printf** (`src/debug.h`) — formatted print output visible in the Emulicious console.
  Build with `make build-debug DEBUG_TRACE=1`: `DEBUG=1` alone adds symbols, not code.
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
  `static` variables appear in none of the three. Since #588 they do not have to be `static`:
  `DBG_STATIC` (`src/debug.h`) is `static` in a release ROM and empty in a debug ROM, and every
  mutable file-scope data declaration in `src/*.c` uses it. Build `make build-debug` and point
  the harness at `build/debug/nuke-raider.noi` to watch any module variable by name.
  `tools/dbg_static_lint.py`, which `make test-tools` runs, fails when a new declaration keeps
  the bare `static` keyword. Static functions and `static const` data keep `static` — the first
  because `enter` and `update` each occur 7 times, the second because it sits in ROM and the
  symbol reader accepts WRAM addresses only. `rs_laps` / `rs_cp_next` (`src/race_state.c`) stay
  plain globals (#448), which is why `deep-race` can assert `_rs_laps >= 1` directly. `_rs_laps`
  is `rs_laps[PLAYER_SLOT]`, slot 0 — the array base is the player's byte only because
  `PLAYER_SLOT == 0` (`src/config.h`). Exported-for-assertion variables stay accessor-only for
  game code; a mirror variable is the wrong fix, because a desynced mirror makes the test lie.
- Every run writes `<main work tree>/build/smoketest/<checkout name>/<scenario>/`: `results.json`
  (with a `verdict` field), `trace.jsonl` (WRAM sentinels sampled every 30 frames), and
  checkpoint screenshots. `--all` adds one `all-results.json` holding every scenario's outcome.
  The location is the MAIN work tree, resolved with `git rev-parse --git-common-dir`, and
  namespaced by the checkout directory name so two concurrent runs never overwrite each other's
  evidence; the files survive removal of the worktree that produced them. `--out-dir` overrides
  it.
- Differential debugging: `--ref-rom PATH` re-runs the same scenario against a reference ROM and
  reports the first WRAM divergence by step. If the scenario fails on both ROMs it is reported
  `scenario-invalid` rather than blamed on the game.

- A run with ONE ROM also reports `scenario-invalid`, when a step's `require` field is false
  (#589). A `require` field states what must hold before the action runs. It accepts a state
  name, or a memory comparison. A false one gives the failure kind `precondition`. It never
  gives the verdict `fail`.

- `assert_state` and `wait_state` name a game state instead of a frame count. A state name is
  the short form of a `const State` object: `title`, `overmap`, `prerace`, `playing`, `results`,
  `game_over`, `hub`.

- The harness reads the state out of the WRAM state stack. It matches the address and the bank
  against the `_state_*` names in the `.noi` file. Those WRAM variables stay `static` in the
  release ROM. A scenario that names a state therefore needs `build/debug/nuke-raider.noi`.
  Run `make build-debug` first. Then add `--debug-noi` to the command.

- A scenario that names a state without those symbols stops before frame 0. It reports a usage
  error. No scenario in `tools/scenarios/` names a state, so the ROM gate needs one ROM only.

- `assert_live` divides into `assert_changes` for symbols and `assert_screen_changes` for the
  screen. `assert_live` remains, and means both. The failure kinds are `stale-symbol` and
  `stale-screen`. Each names its own cause.

- Every failure record carries a `context` block. It names the state at the start of the action,
  the state at the failure, and each state change during the action. It adds a one-sentence
  `hint`. During a race, a `context` block with no state change adds more. It gives the car
  position in pixels and in tiles, the drive limits, and the limits the car sits on.
  `tools/scenarios/README.md` describes each field.

Exit codes: `0` pass, `1` run failure, `2` tool or usage error, `3` scenario invalid. Code 3
means the scenario is wrong, not the game. A false `require` field gives it, and so does a
failure on both ROMs. It is returned for a blocking scenario and for a scenario that is not
blocking. A non-blocking scenario that the GAME failed still exits 0 — read
the `verdict` field, never the exit code, for evidence scenarios.

A scenario error during a run does not stop the run (#507). This covers an unknown symbol, an
unknown operator, and a navigation id with no matching track. Any of these becomes that
scenario's failure, and `results.json` records it as `failure.kind` `scenario`. The run
continues with the next scenario.

A blocking scenario then exits `1`. A scenario that is not blocking keeps the exit code at `0`.
A scenario file that does not load is different: the smoketest exits `2` before it starts a
scenario. With
`--ref-rom`, the same error fails on both ROMs, so the verdict is `scenario-invalid` and the
exit code is `3`.

The manifest each run reads (`build/game-manifest.json`) describes every track: its size in tiles
and pixels, the drive limits (`0` to `map_h * 8 - 16`, the rule in `src/vehicle_physics.c`), the
HUD scan line, the lap target, the finish line, and a text grid with one row per map row and one
character per tile. `tile_legend` names the characters and `solid_tile_types` names which types
block a car. A `?` marks a tile whose TSX entry carries no `type` property.

The grid is tile-type granular, not the engine's real collision: `track_collision_mask`
(`src/track_tileset_meta.h`) gives some `TILE_ROAD` diagonal corner tiles partial per-pixel
collision that the grid cannot show. Do not read the grid as exact collision truth, and do not
plan a route from it — that is out of scope for this work.

Two facts about the game that scenarios must respect:

- **The D-pad is the accelerator**, not `A` (`player.c`: `gas` is gated on
  `J_UP|J_DOWN|J_LEFT|J_RIGHT`); `A` fires. A scenario that "holds A to drive" sits still.
- **"Race is live" is `_hp > 0`**, not `racer_active[0]`. `hp` is 0 through boot and menus,
  because `damage_init()` in `state_playing` sets it when a race starts. Index 0 is the slot of
  the player, and the loader of the enemy fills only the slots from 1 up. So `racer_active[0]`
  reads 0 on every track, and not only on Track 1.

`make test-tools` covers the engine itself host-side (no ROM, no PyBoy emulation — though it does
import PyBoy via `screenshot.py`). The two gates are deliberately separate: unit tests verify the
engine, `make smoketest` verifies the ROM.

### The test command mailbox

The debug ROM carries a nine-byte WRAM wire at a fixed address (`src/debug.h`,
`DBG_MB_BASE = 0xDF70`): `ready`, `opcode`, two arguments, a commit byte, an outcome, a detail
byte, an epoch and a torn-commit count. A scenario's `command` action writes a request into it
and waits for the epoch to advance, then reads the outcome back. Every command calls one of the
game's own functions — `debug_mailbox_poll()` dispatches through the same code paths a player's
input would reach, so a scenario cannot create a state the game itself could not enter. Commands
that would break a game invariant (a locked loadout option, a loadout change mid-race, a push at
the state-stack depth limit) are refused with a named reason (`expect` in the scenario), not
silently applied.

A scenario that sends a `command` step must set `"requires_debug_rom": true` at the top level.
Build it with `make build-debug` and point `--rom`/`--map`/`--noi`/`--manifest` at
`build/debug/nuke-raider.gb` and its siblings; `--all` skips such a scenario against a ROM with
no mailbox and reports it `skipped`, while naming it directly with `--scenario` still runs it.
The mailbox lives in bank 30 — see `CLAUDE.md`'s ROM Header section and the "Two ROMs" section
above. Full command list, argument ranges and refusal codes: `tools/scenarios/README.md`.

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

---

## 9. Factory run registry

Every walk-away factory run records itself under the **main** repo root, outside every
worktree, so a run stays explainable after its worktree is deleted.

```
.factory/
  runs/issue-<N>/
    journal.jsonl                   # append-only; the source of truth
    state.json                      # cached projection of the journal
    publish.json                    # what has been published to GitHub (#472)
    publish/                        # staged assets under their published names
    logs/<STAGE>.log                # stage logs, appended by factory_log (#450)
    autopsy/attempt-<k>/            # evidence copied out of a failed attempt
  cache/master-<sha>.gb             # reference ROM per master SHA, lazily filled (#437)
```

`.factory/` is gitignored. Resolution is `dirname(abspath(git rev-parse --git-common-dir))` —
**not** `--show-toplevel`, which returns the *worktree* root from inside a worktree.
`NUKE_FACTORY_REGISTRY` overrides the location for tests and scratch runs.

### Who writes what

| Tool | Role |
|------|------|
| `tools/factory_run.py` | Schema owner; **sole writer of run state and the journal**. Library, not a CLI. |
| `tools/factory_log.py` | **Sole writer of the `logs/` subtree** ([ADR 450](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/470)): tees stage command output into `logs/<STAGE>.log`. |
| `tools/factory_publish.py` | **Sole writer of the GitHub surfaces** ([ADR 472](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/475)): the run issue, the plan issue, the release assets, the spec-issue comment, the Documents-board item fields on both the spec and run issues, and the pull request. Owns `publish.json`. |
| `tools/factory_event.py` | The command-line surface for **writing** an event: a thin wrapper over `factory_run.append_event`. Adds no schema — `--kind` is validated against `factory_run.EVENT_KINDS`. |
| `tools/factory_cache.py` | **Sole writer of `cache/`** (#437 R5): the `origin/master` reference ROM, keyed by commit SHA, filled lazily on the first smoketest failure. |
| `.claude/skills/factory/` | The orchestrator. Writes nothing itself — it calls the tools above and `factory_publish` at every stage transition, gate result and terminal event. |
| `tools/factory_status.py` | Read-only terminal dashboard (`--json`). Writes nothing at all. |
| `tools/factory_report.py` | Deterministic PR body from state + journal. Writes nothing in the registry. |
| `tools/factory_permission_hook.py` | `Notification` hook: records a run blocked on a permission prompt. |
| `tools/deny_gate_hook.py` | Appends a `permission` event at the moment it refuses. |

### Journal and state

The journal is the truth; `state.json` is a cache. `append_event()` writes the journal line
first, then re-saves state atomically (temp file + `os.replace`), so state can lag the journal
by one event and can never lead it. `load_state()` replays the journal whenever state is
missing, unparseable, of a foreign schema version, or behind the journal — a torn write
self-heals instead of being fatal. An unparseable JSONL line is discarded on read, never an
error. Full rationale: [ADR 436](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/468).

Event kinds: `start`, `stage`, `gate`, `decision`, `retry`, `scenario`, `permission`,
`failure`, `finish`. Every event carries `ts`, `issue`, `attempt`, `kind`.

Only `start`, `stage`, and `retry` move `state["stage"]`. A `gate` event carries a `stage`
field recording where that gate ran, but it does not advance the run — a run can show gate
results for BUILD while its stage is still GATE.

A **retry** clears this attempt's gates, scenarios, failure, and finish marker. Decisions and
permission events accumulate across the whole run: both are evidence about the run, not about
one pass.

### Run conditions

| Condition | Meaning |
|-----------|---------|
| `failed` | A terminal failure was recorded. |
| `complete` | The run finished. |
| `stale` | The recorded worktree no longer exists on disk. |
| `idle` | Worktree intact, nothing emitted for 15 minutes. |
| `active` | Emitting normally. |

Terminal conditions outrank `stale`: a finished run legitimately outlives its worktree.
`stale` and `idle` are never collapsed — they call for different actions.

### Determinism contract

All timestamps are UTC ISO-8601 with an explicit offset, produced through the single
`factory_run.clock()` seam that tests inject and both CLIs expose as `--now`. Gates render in
canonical stage order (`GATE → PLAN → BUILD → VERIFY → SHIP`), decisions in journal order,
never dict order. Golden comparison of the PR body is byte-exact, so trailing whitespace and
the final newline are part of the contract.

Because `condition` and `elapsed` are measured against *now*, a dashboard rendered without
`--now` reports live values: a run that a pinned-clock fixture calls `active` reads `idle`
once real time has moved on. That is the seam working, not drift.

### Autopsy bundles

On a terminal failure the evidence is **copied** — never referenced — into
`autopsy/attempt-<k>/`: state, journal, the scenario JSON as executed, smoketest screenshots
and `trace*.jsonl` / `results.json`, and sha256 sums of the ROM under test and the reference
ROM. Stage logs are excluded because they are written straight into the registry (#450) and
already survive.

Assembly is best-effort and **never raises**: `manifest.json` lists every expected artifact as
present or absent-with-reason. An autopsy that dies during a failure destroys the evidence it
exists to preserve.

### Stage logs

`tools/factory_log.py` runs a stage command, appends its merged stdout+stderr to
`runs/issue-<N>/logs/<STAGE>.log` — binary end-to-end, the child's bytes verbatim — and reports
on the console. Logs are append-only within a stage: retries accumulate, each invocation
wrapped in a single-line header and trailer, so `grep '^===== factory-log'` reconstructs the
invocation list with no parser:

```
===== factory-log stage=BUILD attempt=2 started=2026-07-27T12:00:00+00:00 =====
cwd: C:/Code/nuke-raider/.claude/worktrees/factory-log-450
cmd: make clean
----- output -----
<child bytes, verbatim>
===== factory-log stage=BUILD exit=0 ended=2026-07-27T12:01:03+00:00 =====
```

The trailer is the completion signal: its absence means the invocation did not complete —
otherwise indistinguishable from a command that failed silently.

The child's stdout is a **pipe, not a pty**, so `isatty()` is false and TTY-conditional color
and progress rendering are suppressed. That is the documented cost of capture; nothing forces
color back on, which keeps the logs greppable.

The **console** copy is asymmetric (#529). A failing command prints its full output,
byte-identical to the logged body. A passing command prints one summary line —
`factory-log: ok stage=VERIFY exit=0 bytes=12043 lines=118 log=<path> cmd: make` — because the
bytes are already on disk and a passing gate conveys one bit. The log file is unaffected either
way, so the autopsy tail and the published log assets see no difference. `--stream`
(`run_logged(..., stream=True)`) restores the live tee for one invocation; use it when the caller
reads the command's stdout rather than only its exit code. The summary is suppressed whenever the
log sink failed, so the console never goes quiet in favour of a file that was never written.
Buffering also means the console stays silent *while* a command runs: one that hangs or is killed
prints nothing, and the stage log is where to look.

Logging is **fail-open**: the child's exit code is always returned, and each logging failure
(unresolvable registry root, no issue number, unwritable destination, mid-stream write error)
emits exactly one `factory-log: WARNING:` line on stderr. Outside a factory run there is no
issue number, so the helper degrades to a plain runner — one warning, no log file. That
warning is what lets downstream log publication (#437 R11) report "no stage log captured"
instead of silently missing an asset. The child failing to *spawn* is not a logging failure:
it returns 127 and never reports success.

### Commands

```sh
python tools/factory_status.py                          # terminal dashboard
python tools/factory_status.py --json                   # machine-readable
python tools/factory_report.py --issue 436              # PR body to stdout
python tools/factory_report.py --issue 436 --out body.md
python tools/factory_log.py --stage BUILD --issue 450 -- make clean
python tools/factory_log.py --stage BUILD --attempt 2 -- pwsh -NoProfile -Command "make clean; make"
python tools/factory_log.py --stage GATE --issue 529 --stream -- python tools/spec_lint.py --issue 529 --json
python tools/factory_publish.py --issue 437 --run-start
python tools/factory_publish.py --issue 437 --stage-completed BUILD
python tools/factory_publish.py --issue 437 --terminal
python tools/factory_publish.py --issue 437 --dry-run
python tools/factory_event.py --issue 437 --kind stage --field stage=BUILD
python tools/factory_event.py --issue 437 --kind decision --field "text=widened the rule"
python tools/factory_cache.py                           # reference ROM path on stdout
python tools/factory_cache.py --print-only              # cache path, never builds
```

`factory_status` and `factory_report` exit `0` whenever they render and `2` on operational
failure; neither ever exits `1` from run content — an unhealthy run is a thing to report, not
a tool error. `factory_log` passes the child's exit code through verbatim, returns `127` when
the command cannot be spawned, and `2` on misuse (unknown `--stage`, bad `--now`, no command
after `--`). On success it prints only a summary line; `--stream` restores the full output.
Commands are argv lists — never `shell=True`; a compound command names its shell
explicitly, as in the `pwsh -NoProfile -Command` example above.

`factory_event` exits `0` when the event is appended and `2` on misuse (unknown kind, malformed
`--field`, bad `--now`) — it never exits `1`, because a run's content is never this tool's
error. `factory_cache` exits `0` with the ROM path on stdout, `1` when the reference build
itself failed, and `2` when it could not run.

### Publishing to GitHub

A run's durable, shareable rendering is a **run issue** on GitHub, written only by
`tools/factory_publish.py`
([ADR 472](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/475)).
One run issue per **spec** issue — created on the first publish,
reused forever after, reopened when a later attempt starts, closed at terminal. Its number
lives in `publish.json`, so it is never recreated. It carries the `log` label and sits in the
"Nuke Raider — Documents" project with **Type = Log** and `Status = In Progress`, moving to
`Done` at terminal, which is what the
[Logs view](https://github.com/users/MatthieuGagne/projects/3/views/4) filters on (sorted by
*Updated*, not *Created*: a run issue is long-lived, so most-recently-active first is what a
dashboard wants).

The title is the dashboard — in an issue list it is the only column there is:

```
run 437 · attempt 2 · BUILD · active
```

`<condition>` is `factory_status.condition()` verbatim; there is one definition of the five
conditions, not two.

**Cadence.** Publication is an explicit call, never a side effect of `append_event()`. The
orchestrator calls it at stage transitions, gate results and terminal events — roughly 15-25
edits per run. `factory_run` performs no network I/O at all: a GitHub outage must never stall a
stage or slow the journal's hot path, so the published copy is **allowed to lag** and the local
registry stays the authority.

**Assets.** Stage logs publish as per-attempt assets on a rolling `factory-logs` release, named
`issue-<N>-attempt-<k>-<stage>.log` and never clobbered. Each is a verbatim whole-file copy of
`logs/<stage>.log` as it stood at upload time — the publisher copies bytes and never reads log
content, so #450's no-parsing boundary is untouched. Because local logs are append-only across
attempts, attempt *k*'s asset is a superset of attempt *k−1*'s; that redundancy buys an
immutable per-attempt history and is an accepted cost. Screenshots publish uncapped as
`issue-<N>-attempt-<k>-<scenario>-<frame>.png` and render inline in the body. The plan asset is
the one deliberate exception to "never clobbered": it is a mirror of a file that keeps changing
during BUILD, so `issue-<N>-plan.md` is re-uploaded with `--clobber` and a later attempt's plan
replaces an earlier one in place, rather than accumulating per-attempt history like the other
assets.

**The withheld case.** Before upload every log **and the plan** is matched against a short
denylist of credential shapes (`gh[pousr]_`, `github_pat_`, `xox[baprs]-`, `AKIA…`, long `Bearer`
values). A hit on a stage log **blocks that one asset** and the body's Stage logs row says so,
naming the local path. A hit on the plan additionally empties the plan issue's summary — the
scan guards the indexed issue body, not just the asset — but the plan asset does **not** appear
in the Stage logs row; its withheld state is reported only on the plan issue itself. Everything
published stays byte-exact: redaction would make that invariant conditional and one false
positive would silently corrupt a log. This is the only net there is — the repo is public and
GitHub's push protection does not inspect release assets.

**Bounds.** The body is rendered, measured and shed until it fits under 60,000 characters
(GitHub's cap is ~65k): first the inline log tail, then permission events, then decisions
oldest-first, each cut leaving an explicit marker. The status header, stage strip, failure
fields, gate table and stage-log table are never shed. A body edit rejected for length would
freeze the dashboard exactly when a run is going wrong, so the bound is enforced by the renderer
rather than discovered from an API error.

**Fail-open, end to end.** No publication failure — issue create/edit, asset upload, label,
project, comment — changes a run's outcome. Each degradation emits exactly one
`factory-publish: WARNING:` line on stderr and is reported in the body where the body is still
writable. The tool exits `1` when it published with degradation; **the orchestrator must not
treat that as a run failure.**

### Permission events

A permission prompt during an unattended run is an allowlist bug (#432 R6). Two mechanisms
record it: the `Notification` hook captures a run blocked on a prompt, and `deny_gate_hook.py`
appends at the moment it refuses. Correlation is by `NUKE_FACTORY_RUN` carrying the **issue
number** (`NUKE_FACTORY_RUN=436`) — not by `cwd`, which matches every run equally and does not
exist yet at GATE stage. A non-numeric value stays truthy, so the deny gate's factory-only
rules still fire while the run is treated as unattributable and nothing is journalled; that is
how the deny-gate tests exercise the rules without writing to the real registry. It is set by
the session or driver process, never by a settings file: the repo tier forbids `env` (see
[ADR 443](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/466)).

Note that the deny gate matches on raw command text, so a diagnostic that merely *quotes* a
forbidden command is itself refused. Assemble such strings piecewise in tooling that reports
on denied commands.

This is the one agent-specific surface here. Under any other agent no permission events are
recorded, and a run with none renders as normal, not broken.

### Reference-ROM cache

VERIFY's blocking smoketest can diff a run against a reference ROM built from `origin/master`
and report the first WRAM divergence (`--ref-rom`). That divergence is where a smoketest
diagnosis starts — the project's two-ROM doctrine, never code inspection alone.

The reference costs a full clean build, and only the failure path consumes it, so the cache is
filled **lazily**: `tools/factory_cache.py` is called only after the blocking smoketest has
already failed. It resolves `origin/master`, and on a miss builds that SHA in a temporary
detached worktree under `cache/`, copies the ROM to `cache/master-<sha>.gb`, and removes the
temporary tree. A second failure on the same master reuses the cached ROM for free.

The cache is a Python tool rather than inline shell for a reason that is not stylistic: the deny
gate's `FACTORY_ONLY` rules refuse `git worktree remove` for any shell tool call made while
`NUKE_FACTORY_RUN` is set. A `PreToolUse` hook sees tool calls, not the `subprocess` calls made
inside one, so the temporary tree can be cleaned up here and nowhere else.

Exit codes: `0` the ROM path is on stdout (hit or fill), `1` the reference build failed, `2` the
tool could not run at all.

### Retention

None. `.factory/` grows without bound from screenshots, traces, stage logs, staged assets and
**cached reference ROMs — one per distinct `origin/master` SHA that a run has diagnosed
against** — until deleted by hand, and GitHub release assets grow with it: one flapping spec
accumulates per-attempt assets indefinitely. Deleting old assets is always safe because the
local registry is the source of truth (#450 R5), and deleting `cache/` is always safe because it
refills lazily. No automatic policy is specified. Accepted cost for a solo project.

## 10. House style

Write factory-authored GitHub text, PRD bodies, plan documents and repository docs in plain
English:

1. Short sentences, one idea each.
2. Active voice — name the actor. "The linter reports", not "findings are reported".
3. Simple tense. "The gate failed", not "the gate has failed".
4. Concrete verbs, plain words.
5. Use the term `CONTEXT.md` defines. An `_Avoid_` ban wins even when the banned word is plainer.

Two exemptions. Game text follows `docs/STORY_BIBLE.md`, not this section. **Verbatim tool output
is quoted as-is** — simplifying a quoted `make` error falsifies it.

This is guidance, not a gate. There is no linter and nothing fails a build over it. #517 shipped an
`ste_lint.py` plus a 3.6k-line baseline; the `--all` form could not fail by construction, so it
caught nothing while charging a rebaseline for every documentation change. Both are now deleted.

### Decision fields

A factory `decision` event carries two fields:

| Field | Holds | Length |
|---|---|---|
| `text` | The ruling | One sentence |
| `rationale` | The reasoning | One to three sentences |

```bash
python tools/factory_event.py --issue 517 --kind decision \
  --field "text=Keep the smaller change." \
  --field "rationale=The alternative moves four files and two golden fixtures."
```

`rationale` is optional. The run issue and the pull request body render a decision that has one as
a bold summary plus a collapsed `<details>` block, and a decision that has none as a plain bullet —
so a journal written before the split still renders. `SCHEMA_VERSION` stays at 1 and no journal is
migrated.

`factory_event.py` enforces neither length. Both are guidance: an unrecorded decision is a worse
outcome than a long one.
