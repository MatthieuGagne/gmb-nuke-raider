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

---

## 2. Branch & Worktree Policy

- **Never commit directly to `master`.** All work goes on a feature branch and merges via PR.
- **Always work inside a git worktree.** Every file operation — create, edit, delete — must
  happen in a worktree. Use `EnterWorktree` or the `using-git-worktrees` skill before any write.
- **Integrate via PR only.** Never merge feature branches to master locally.
- Use `gh` for all GitHub operations. Run `gh auth setup-git` if push fails.
- `.claude/settings.local.json` is checked into git; commit it alongside feature work.

---

## 3. Outer Dev Loop

```
brainstorming skill
  → /prd skill (creates GitHub issue with PRD)
  → [new session] writing-plans skill (creates docs/plans/YYYY-MM-DD-<feature>.md)
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
4. `GBDK_HOME=/home/mathdaman/gbdk make` → ROM builds
5. Invoke `bank-post-build` skill (hard gate)
6. Run refactor checkpoint: "Does this generalize, or hard-coded for N=1?"
7. Invoke `gb-c-optimizer` agent on new/modified C files
8. Commit

**Consultation mode** (API questions, hardware register questions): call `gbdk-expert` agent without the "implement this task:" prefix — it answers as normal.

### Non-C tasks (docs, Python, JSON, assets)

Write → verify → commit. No bank gates required.

---

## 4. Build & Test Gates

### Test runner

```bash
make test                # C unit tests (gcc + Unity, no GBDK needed)
make test-tools          # Python tool tests (png_to_tiles, tmx_to_c)
make test-integration    # headless PyBoy regression suite (builds debug ROM first)
```

`make test-integration` boots the debug ROM once and navigates every game state (title → overmap → hub → playing → game_over → title). Update `tests/integration/test_regression.py` when game states or navigation change — always ask the user first.

### ROM build

```bash
GBDK_HOME=/home/mathdaman/gbdk make
make clean && GBDK_HOME=/home/mathdaman/gbdk make   # clean build (required before smoketest)
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

For **runtime issues** (crashes, glitches, wrong values): invoke the `emulicious-debug` skill.

Key tools in Emulicious:
- **EMU_printf** (`src/debug.h`) — formatted print output visible in the Emulicious console
- **Step-through debugger** — breakpoints, register inspection, memory viewer
- **Tile/sprite viewers** — verify VRAM contents, OAM state, palette assignments
- **Tracer + profiler** — identify hot paths and timing issues

Launch command (from worktree directory):
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

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
- [ ] `bank-post-build` skill passes (no FAIL banks)
- [ ] `make memory-check` passes (no FAIL/ERROR budgets)
- [ ] Smoketest in Emulicious confirmed by user
- [ ] `git fetch origin && git merge origin/master` merged from latest master
- [ ] Clean build (`make clean && GBDK_HOME=/home/mathdaman/gbdk make`) succeeds
- [ ] **If user-visible behavior changed:** README module table updated
- [ ] **If any `.claude/skills/`, `.claude/agents/`, or `CLAUDE.md` file changed:** this file (`docs/dev-workflow.md`) updated
- [ ] PR body includes `Closes #N` for the related issue
- [ ] `.claude/settings.local.json` committed if any new tool permissions were approved

Use `gh pr create` with a `## Summary` + `## Test Plan` body. After merge, verify the linked
issue is auto-closed; if not, run `gh issue close N`.
