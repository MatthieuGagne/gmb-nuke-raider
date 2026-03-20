# Full Autobank Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate all manual ROM bank pins and SET_BANK-from-BANKED-function violations so bankpack assigns every file automatically, matching the Black Castle reference architecture.

**Architecture:** Phase 0 updates all skills/agents/docs/memories (hard prerequisite — `bank-pre-write` would BLOCK valid Phase 1 writes without this). Phase 1 implements the code changes: `loader.c` NONBANKED wrappers, `invoke()` state dispatch, portrait unpinning, and `png_to_tiles.py` BANKREF fix.

**Tech Stack:** GBDK-2020 / SDCC, MBC5 (`-Wm-yt25`), `-autobank`, `bankpack`, Python 3 (png_to_tiles.py, bank_check.py), Unity (host tests), gcc.

---

## Phase 0 Status: ✅ COMPLETE (2026-03-18)

All Phase 0 tasks merged. Phase 1 code can now be written.

| Task | Status | Commit |
|------|--------|--------|
| 0-A: Rewrite bank-pre-write skill | ✅ done | c488fdf |
| 0-B: Update sprite-expert skill | ✅ done | 36d6356 |
| 0-C: Update gbdk-expert agent | ✅ done | 8a63be1 |
| 0-D: Update CLAUDE.md | ✅ done | 0979fde |
| 0-E: Rewrite memory files | ✅ done | (outside repo) |
| 0-F: Verify + final commit | ✅ done | (see git log) |

---

## ✅ Phase 0 complete — Phase 1 is unblocked

The `bank-pre-write` skill has been updated. Phase 1 code writes that use `#pragma bank 255` for state files and portrait files will now pass the skill gate. Pull the latest `master` into your worktree before starting Phase 1.

---

## Phase 0 — Update skills, agents, docs, and memories

### Task 0-A: Rewrite `bank-pre-write` skill

**Files:**
- Modify: `.claude/skills/bank-pre-write/SKILL.md`

**Current state:** Check 1 mandates bank 1 for `state_*.c` and bank 2 for `npc_*_portrait.c`. Check 3 permitted-callers list omits `loader.c`. Check 5 says "portraits pinned via `--bank 2`".

**Step 1: Edit the skill**

Replace the entire file content. Key changes:
- **Check 1:** Remove bank-1 mandate for `state_*.c` and bank-2 mandate for `npc_*_portrait.c`. New rule: only `bank 0` is architecturally mandated (for files that call SET_BANK/SWITCH_ROM). All others use `bank 255` (autobank) or the bank documented in `bank-manifest.json`.
- **Check 3:** Update permitted SET_BANK/SWITCH_ROM caller list: `main.c`, `music.c`, `hub_data.c`, `state_hub.c`, `state_overmap.c`, `loader.c`.
- **Check 5:** Change portrait note from "`--bank 2` for portraits" to "`--bank 255` for all generated asset files; use explicit `--bank N` only for architecturally justified overrides".

New content for `.claude/skills/bank-pre-write/SKILL.md`:

```markdown
---
name: bank-pre-write
description: Hard gate — invoke before writing any src/*.c or src/*.h file. Validates bank manifest, pragma, and SET_BANK safety.
---

# Bank Pre-Write Gate

**STOP.** Before writing or editing any `src/*.c` or `src/*.h` file, run the checks below. For `.c` files: all 5 checks apply. For `.h` files: Checks 3, 4, and 5 apply (headers carry no `#pragma bank`; the manifest covers `.c` files only).

## Check 1 — Manifest entry exists

Read `bank-manifest.json` at the repo root.

- If the file you are about to write is a `.c` file and is NOT in the manifest → **BLOCK**:
  > "Add an entry to `bank-manifest.json` for `src/<file>.c` before writing it. Specify bank number (255 for autobank, 0 for HOME bank code that calls SET_BANK/SWITCH_ROM) and reason."

- If creating a new `state_*.c` file → manifest bank **must** be 255 (autobank), unless it calls SET_BANK/SWITCH_ROM in which case it must be 0.
- If creating a new `npc_*_portrait.c` file → manifest bank **must** be 255 (autobank); loader.c handles bank switching.

## Check 2 — Pragma matches manifest

Look up the file's expected bank in `bank-manifest.json`.

| Manifest bank | Required in first 5 lines of `.c` file |
|---------------|----------------------------------------|
| 0             | No `#pragma bank` line at all |
| 255           | `#pragma bank 255` |
| N (any other) | `#pragma bank N` |

If the pragma you are about to write doesn't match → **BLOCK and correct it before writing.**

## Check 3 — No `SET_BANK` or `SWITCH_ROM` inside banked code

If the file's manifest bank is **not 0** (i.e., it lives in the switchable window 0x4000–0x7FFF):

- **BLOCK** any `SET_BANK(...)` or `SWITCH_ROM(...)` call inside that file.
  > Reason: calling SET_BANK/SWITCH_ROM from banked code switches the window away from the running function → crash.
  > Fix: move the SET_BANK call into `loader.c` (a bank-0 NONBANKED wrapper), or into another bank-0 file.

Only these bank-0 files may call `SET_BANK`/`SWITCH_ROM`: `main.c`, `music.c`, `hub_data.c`, `state_hub.c`, `state_overmap.c`, `loader.c`.

## Check 4 — No `BANKED` on static functions or bank-0 functions

- `static` functions must NOT be `BANKED` — they cannot be called cross-bank anyway.
- Bank-0 functions must NOT be `BANKED` — they're always mapped; the keyword generates useless trampoline overhead.
- Function pointer fields in structs must NOT be `BANKED` — SDCC generates broken double-dereference code. Use plain `void (*fn)(void)`.

## Check 5 — Makefile `--bank` flags consistent

All generated asset files use `--bank 255` (autobank). Use `--bank N` only for architecturally justified overrides (documented in `bank-manifest.json`).

If adding a new generated file, ensure the Makefile passes `--bank 255` to `png_to_tiles.py` and the manifest entry is `bank: 255`.

## If all checks pass

Proceed with writing the file. Announce: "bank-pre-write: all checks passed for `src/<file>.c` (bank N)."
```

**Step 2: Commit**

```bash
git add .claude/skills/bank-pre-write/SKILL.md
git commit -m "docs: update bank-pre-write skill for autobank migration (phase 0)"
```

---

### Task 0-B: Update `sprite-expert` skill

**Files:**
- Modify: `.claude/skills/sprite-expert/SKILL.md`

**Step 1: Find line 22 and the pipeline table**

The line currently reads: `portraits use '2'` in the --bank column.

**Step 2: Edit the file**

Change: `portraits use \`2\`` → `portraits use \`255\` (autobank)`

Also add a note to Step 5 (set_sprite_data / set_bkg_data section): `set_sprite_data` / `set_bkg_data` calls that load banked tile data must be made from bank-0 code (via loader.c wrappers), not from within banked callers.

**Step 3: Commit**

```bash
git add .claude/skills/sprite-expert/SKILL.md
git commit -m "docs: update sprite-expert skill — portraits use autobank 255"
```

---

### Task 0-C: Update `gbdk-expert` agent

**Files:**
- Modify: `.claude/agents/gbdk-expert.md`

**Step 1: Read the current file**

Read `.claude/agents/gbdk-expert.md` to find the stale metadata section.

**Step 2: Fix stale project metadata**

Change in the Project Context section:
- `JUNK RUNNER` → `NUKE RAIDER`
- `MBC1 (\`-Wm-yt1\`)` → `MBC5 (\`-Wm-yt25\`)`
- `build/junk-runner.gb` → `build/nuke-raider.gb`
- Memory path: `gmb-junk-runner` → `gmb-nuke-raider`

**Step 3: Add banking architecture section**

Add a new section after Domain Knowledge:

```markdown
### Banking Architecture (post-autobank-migration)

**Invariant:** Only bank-0 files (no `#pragma bank`) may call `SET_BANK` or `SWITCH_ROM`.
Files with `#pragma bank 255` (autobank) or explicit bank: call BANKED functions or NONBANKED loader wrappers — never touch `SWITCH_ROM` directly.

**loader.c pattern:** bank-0 NONBANKED wrappers for all VRAM asset loads:
```c
void load_player_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(player_tile_data));
    set_sprite_data(0, PLAYER_TILE_COUNT, player_tile_data);
    SWITCH_ROM(saved);
}
```

**invoke() state dispatch pattern:** state_manager.c (bank 0) holds:
```c
static void invoke(void (*fn)(void), uint8_t bank) {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(bank);
    fn();
    SWITCH_ROM(saved);
}
```
State struct carries a `uint8_t bank` field. Callbacks are plain function pointers (not BANKED — SDCC generates broken double-dereference for BANKED struct field pointers).

**BANKREF for autobank:** `BANKREF(sym)` is linker-resolved by bankpack to the real assigned bank. Use `BANKREF` for `#pragma bank 255` files. `volatile __at(N)` is only correct for explicit bank N (not 255), and only in data-only files where loader.c does NOT use `BANK(sym)` to switch.
```

**Step 4: Commit**

```bash
git add .claude/agents/gbdk-expert.md
git commit -m "docs: update gbdk-expert agent — fix stale metadata, add autobank architecture"
```

---

### Task 0-D: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Fix ROM Header section**

Find: `-Wm-yt1` (MBC1), `"JUNK RUNNER"`
Replace: `-Wm-yt25` (MBC5), `"NUKE RAIDER"`

**Step 2: Fix Memory budgets section**

Find: `ROM: MBC1 up to 1 MB`
Replace: `ROM: MBC5, 32 banks declared (\`-Wm-ya32\`), up to 512 KB addressable`

**Step 3: Clarify Parallel agents policy**

Add concrete examples to the parallel agents policy bullet:
```
- ✅ Safe to parallelize: multiple file audits; implementing loaders for independent systems (different output files); skill/agent doc updates (different files); read-only exploration
- ❌ Not safe: writing the same file; multiple actors committing to the same branch; tasks with sequential data dependencies
```

**Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md — fix MBC5/NUKE RAIDER metadata, clarify parallel agent policy"
```

---

### Task 0-E: Update memory files

**Files:**
- Modify: `~/.claude/projects/-home-mathdaman-code-gmb-nuke-raider/memory/feedback_rom_banking.md`
- Modify: `~/.claude/projects/-home-mathdaman-code-gmb-nuke-raider/memory/feedback_rom_banking_overflow.md`
- Modify: `~/.claude/projects/-home-mathdaman-code-gmb-nuke-raider/memory/gbdk-expert.md`
- Modify: `~/.claude/projects/-home-mathdaman-code-gmb-nuke-raider/memory/MEMORY.md`

**Step 1: Rewrite `feedback_rom_banking.md`**

```markdown
---
name: ROM banking — autobank architecture invariant
description: Only bank-0 files may call SET_BANK/SWITCH_ROM; state dispatch uses invoke() pattern; blank screen = SET_BANK in banked file, not bank-1 overflow
type: feedback
---

Only bank-0 files (no `#pragma bank`) may call `SET_BANK` or `SWITCH_ROM`. Files with `#pragma bank 255` or explicit bank N: use BANKED functions or call NONBANKED wrappers in `loader.c`.

**Why:** Any `#pragma bank` file executes from the switchable ROM window (0x4000–0x7FFF). Calling `SWITCH_ROM` there unmaps the running code → CPU crash → blank screen. The old fix of pinning state code to bank 1 was fragile — it relied on coincidence that caller and data were in the same bank.

**How to apply:**
- State callbacks: `#pragma bank 255` (autobank), export `const State s = { .bank = BANK(s), .enter = enter, ... }`. `state_manager.c` is bank 0, uses `invoke()` to switch banks.
- VRAM asset loads: add NONBANKED wrapper to `loader.c`, call it from banked init functions.
- Blank screen → check `grep SET_BANK src/*.c` for violations in banked files (not just bank-1 overflow).
- `bank-post-build` still validates bank budget; `bank_check.py` still validates pragmas.
```

**Step 2: Rewrite `feedback_rom_banking_overflow.md`**

```markdown
---
name: feedback_rom_banking_overflow
description: Data files no longer need manual bank pins; loader.c NONBANKED wrappers let bankpack assign data anywhere safely
type: feedback
---

Data files no longer need manual bank pins (`--bank 2`, `--bank 3`, etc.). Use `--bank 255` (autobank) for all generated asset files. `loader.c` NONBANKED wrappers (`SWITCH_ROM` from bank 0) let bankpack assign data to any bank safely.

**Why:** The old overflow fix — pinning large files to bank 2+ — was a bandage on a root cause. The real bug was `SET_BANK` inside BANKED functions (player.c, track.c). Now those calls are replaced by `load_player_tiles()` / `load_track_tiles()` in `loader.c` (bank 0). Bank-0 code can safely switch to any bank.

**How to apply:**
- New asset files → `--bank 255` and manifest `bank: 255`.
- Never put `SET_BANK` / `SWITCH_ROM` inside a `#pragma bank` file.
- `bank-post-build` warns at >90% bank fill; `bank_check.py` blocks SET_BANK-in-banked violations (after P1-R9 lint rule is added).
```

**Step 3: Update `gbdk-expert.md` memory**

Append two updated entries (or replace stale entries):

Replace: "volatile __at(255) is the correct replacement for BANKREF" entry →
```
## BANKREF vs volatile __at — which to use

- `#pragma bank N` (explicit, N ≠ 255), data-only file, loader.c uses SET_BANK to reach it: use `volatile __at(N) uint8_t __bank_sym;` — hardcodes N at compile time, correct for explicit assignment.
- `#pragma bank 255` (autobank): use `BANKREF(sym)` — bankpack rewrites `___bank_sym` to the actual assigned bank at link time. `volatile __at(255)` makes `BANK()` return 255 (wrong after autobank migration, since loader.c uses `BANK(sym)` to actually switch banks).
```

Replace: "Blank screen / ~1-2 FPS = state code overflowed bank 1" entry →
```
## Blank screen / ~1-2 FPS = crash symptom

Root cause is almost always `SET_BANK`/`SWITCH_ROM` called from inside a `#pragma bank` file (banked code). Check: `grep -n "SET_BANK\|SWITCH_ROM" src/*.c | grep -v "loader\.c\|state_hub\.c\|state_overmap\.c\|main\.c\|music\.c"` — any output = crash source. Fix: move the call to loader.c or another bank-0 wrapper.
```

**Step 4: Update MEMORY.md index**

Update the two feedback entries in MEMORY.md to reflect the new descriptions.

**Step 5: No commit needed** — memory files are outside the repo. Changes take effect immediately.

---

### Task 0-F: Verify Phase 0

**Step 1: Run tests to ensure nothing is broken**

```bash
cd /path/to/worktree
make test && make test-tools
```
Expected: all pass (no code changes yet, tests should be green).

**Step 2: Build to confirm bank_check still works**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: clean build.

**Step 3: Commit everything and push**

```bash
git add -A
git status  # review
git commit -m "chore: phase 0 complete — update all skills/agents/docs/memories for autobank migration"
```

---

## Phase 1 Status: ⚠️ CODE COMPLETE, SMOKETEST FAILED (2026-03-18)

All Phase 1 code tasks (1-A through 1-J) are complete. All acceptance criteria (AC1–AC10) pass. Smoketest in Emulicious showed the ROM is broken at runtime. Debug required before PR can be created.

**Next session:** Run `emulicious-debug` skill to diagnose the runtime failure. The ROM builds clean, all host tests pass, bank-post-build passes — the issue is runtime behavior.

| Task | Status | Commit |
|------|--------|--------|
| 1-A: Fix png_to_tiles.py BANKREF | ✅ done | a93d5b8 |
| 1-B: bank_check SET_BANK lint rule | ✅ done | e791ebf |
| 1-C: Create loader.c / loader.h | ✅ done | 75b1b2c |
| 1-D: Remove SET_BANK from player.c | ✅ done | 199b1df |
| 1-E: Remove SET_BANK from track.c | ✅ done | 0fa7a9e |
| 1-F: camera.c track_get_raw_tile() | ✅ done | 2f9a53d |
| 1-G: state_manager.c bank-0 invoke() | ✅ done | 3b6d053 |
| 1-H: State callbacks BANKREF+bank field | ✅ done | 13911f6 |
| 1-I: Unpin portraits + dialog_border | ✅ done | 68d0ec1 |
| 1-J: Final verification (all ACs pass) | ✅ done | — |
| 1-K: Smoketest + PR | ❌ BLOCKED — runtime failure | — |

**Known implementation detail:** `BANKREF(x)` + `BANKREF_EXTERN(x)` are both needed in the defining file to use `BANK(x)` in static initializers (SDCC only emits the ASM stub from BANKREF, not a C declaration). Bank-0 State files (state_hub, state_overmap) use literal `0` instead of `BANK()` since BANK() does not work for HOME-bank files in SDCC.

---

## Phase 1 — Implement autobank migration

**⚠️ STOP:** Do not start Phase 1 until Phase 0 PR is merged and you have pulled the latest master into this worktree:
```bash
git fetch origin && git merge origin/master
```

---

### Task 1-A: Fix `png_to_tiles.py` — BANKREF for autobank

**Files:**
- Modify: `tools/png_to_tiles.py`
- Modify: `tests/test_png_to_tiles.py`

**Why first:** The portrait regeneration in P1-E depends on the fixed generator. Also, changing the test first (TDD) makes the requirement explicit before touching the generator.

**Step 1: Write the failing tests**

In `tests/test_png_to_tiles.py`, change the two existing `volatile __at` tests to expect `BANKREF`:

Replace `test_bank_ref_uses_volatile_at_255`:
```python
def test_bank_ref_uses_bankref_for_autobank(self):
    """BANKREF(sym) emitted for --bank 255 (autobank) — bankpack resolves real bank at link time."""
    data = _make_indexed_png(8, 8, [1] * 64)
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as pf:
        pf.write(data)
        png_path = pf.name
    with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w') as cf:
        c_path = cf.name
    png_to_c(png_path, c_path, 'my_tiles', bank=255)
    with open(c_path) as f:
        src = f.read()
    self.assertIn('BANKREF(my_tiles)', src)
    self.assertNotIn('volatile __at(255)', src)
```

Keep `test_bank_ref_uses_volatile_at_explicit_bank` unchanged (explicit bank N still uses volatile __at).

Add a new test for explicit bank 2:
```python
def test_bank_ref_uses_volatile_at_bank2(self):
    """volatile __at(2) still emitted for explicit --bank 2."""
    data = _make_indexed_png(8, 8, [1] * 64)
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as pf:
        pf.write(data)
        png_path = pf.name
    with tempfile.NamedTemporaryFile(suffix='.c', delete=False, mode='w') as cf:
        c_path = cf.name
    png_to_c(png_path, c_path, 'my_tiles', bank=2)
    with open(c_path) as f:
        src = f.read()
    self.assertIn('volatile __at(2) uint8_t __bank_my_tiles;', src)
    self.assertNotIn('BANKREF', src)
```

**Step 2: Run to verify tests fail**

```bash
cd /path/to/worktree
PYTHONPATH=. python3 -m unittest tests.test_png_to_tiles -v
```
Expected: `test_bank_ref_uses_bankref_for_autobank` FAIL ("BANKREF(my_tiles) not found in output").

**Step 3: Update `png_to_tiles.py`**

In the `png_to_c` function, replace the bank reference generation block:

Current (lines ~170-173):
```python
"/* Bank reference: volatile __at(bank) places the bank symbol in DATA (not CODE),",
"   so bankpack assigns it to the same bank as this file's data array.",
"   BANKREF() creates a CODE stub that bankpack may assign to a different bank. */",
f"volatile __at({bank}) uint8_t __bank_{array_name};",
```

New logic:
```python
# Bank reference generation:
# --bank 255 (autobank): use BANKREF(sym) so bankpack rewrites ___bank_sym to
#   the real assigned bank at link time. This is required when bank-0 code
#   (loader.c) uses BANK(sym) to actually switch banks — volatile __at(255)
#   would make BANK() return 255 (wrong after bankpack assigns a real bank).
# --bank N (explicit): use volatile __at(N) — hardcodes N at compile time,
#   correct for explicit bank assignment.
```

Then in the `lines` list:
```python
if bank == 255:
    lines += [
        "/* Bank reference: BANKREF(name) emits a CODE stub; bankpack rewrites",
        "   ___bank_name to the actual assigned bank at link time.",
        "   Required for autobank (255) so BANK(name) returns the real bank. */",
        f"BANKREF({array_name})",
        "",
    ]
else:
    lines += [
        f"/* Bank reference: volatile __at({bank}) hardcodes bank number N.",
        "   Correct for explicit bank assignment where BANK(sym) = N. */",
        f"volatile __at({bank}) uint8_t __bank_{array_name};",
        "",
    ]
```

**Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. python3 -m unittest tests.test_png_to_tiles -v
```
Expected: all pass.

**Step 5: Commit**

```bash
git add tools/png_to_tiles.py tests/test_png_to_tiles.py
git commit -m "fix: png_to_tiles.py — emit BANKREF for --bank 255, volatile __at only for explicit banks"
```

---

### Task 1-B: Add SET_BANK-in-banked lint rule to `bank_check.py`

**Files:**
- Modify: `tools/bank_check.py`
- Modify: `tests/test_bank_check.py`

**Step 1: Write the failing test**

Add to `tests/test_bank_check.py`:

```python
def test_set_bank_in_banked_file_is_error(self):
    """A #pragma bank 255 file containing SET_BANK is an error."""
    with tempfile.TemporaryDirectory() as d:
        manifest = {'src/foo.c': {'bank': 255, 'reason': 'autobank'}}
        self._write_manifest(d, manifest)
        self._write_c(d, 'foo.c', [
            '#pragma bank 255',
            '#include "banking.h"',
            'void foo(void) BANKED {',
            '    SET_BANK(bar_data);',
            '    use(bar_data);',
            '    RESTORE_BANK();',
            '}',
        ])
        errors = bank_check.check(d)
    self.assertEqual(len(errors), 1)
    self.assertIn('SET_BANK', errors[0])
    self.assertIn('foo.c', errors[0])

def test_switch_rom_in_banked_file_is_error(self):
    """A #pragma bank 255 file containing SWITCH_ROM is an error."""
    with tempfile.TemporaryDirectory() as d:
        manifest = {'src/foo.c': {'bank': 255, 'reason': 'autobank'}}
        self._write_manifest(d, manifest)
        self._write_c(d, 'foo.c', [
            '#pragma bank 255',
            'void foo(void) BANKED {',
            '    SWITCH_ROM(2);',
            '}',
        ])
        errors = bank_check.check(d)
    self.assertEqual(len(errors), 1)
    self.assertIn('SWITCH_ROM', errors[0])

def test_set_bank_in_bank0_file_is_ok(self):
    """A bank-0 file may freely call SET_BANK."""
    with tempfile.TemporaryDirectory() as d:
        manifest = {'src/loader.c': {'bank': 0, 'reason': 'HOME bank'}}
        self._write_manifest(d, manifest)
        self._write_c(d, 'loader.c', [
            '/* no pragma */',
            'void load_tiles(void) {',
            '    SET_BANK(tile_data);',
            '    set_bkg_data(0, 10, tile_data);',
            '    RESTORE_BANK();',
            '}',
        ])
        errors = bank_check.check(d)
    self.assertEqual(errors, [])
```

**Step 2: Run to verify tests fail**

```bash
PYTHONPATH=. python3 -m unittest tests.test_bank_check -v
```
Expected: the three new tests FAIL.

**Step 3: Add lint rule to `bank_check.py`**

In the `check()` function, after the existing pragma check, add:

```python
        # Check 2b: no SET_BANK/SWITCH_ROM in banked files
        if expected_bank != 0:
            with open(abs_path) as f:
                content = f.read()
            if 'SET_BANK' in content or 'SWITCH_ROM' in content:
                errors.append(
                    f"ERROR: {rel_path} contains SET_BANK or SWITCH_ROM but is not bank 0 "
                    f"(bank {expected_bank}). Only bank-0 files may call these. "
                    f"Move to loader.c or another bank-0 wrapper."
                )
```

Note: the content check reads the full file. The existing code reads only the first 5 lines for pragma checking, so add a separate full-file read here.

**Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. python3 -m unittest tests.test_bank_check -v
```
Expected: all pass.

**Step 5: Run full test suite**

```bash
make test && make test-tools
```
Expected: all pass. (Note: the existing codebase has `player.c` and `track.c` with `SET_BANK` in `#pragma bank 255` files — these will now FAIL `bank_check`, which is correct. The build will fail until P1-C and P1-D fix them. That's the point.)

**Step 6: Verify the build now fails correctly**

```bash
GBDK_HOME=/home/mathdaman/gbdk make 2>&1 | head -20
```
Expected: build fails with errors about `SET_BANK` in `player.c` and `track.c`. This confirms the lint rule is working.

**Step 7: Commit**

```bash
git add tools/bank_check.py tests/test_bank_check.py
git commit -m "feat: bank_check.py — lint rule blocks SET_BANK/SWITCH_ROM in banked files"
```

---

### Task 1-C: Create `src/loader.c` and `src/loader.h`

**Files:**
- Create: `src/loader.c`
- Create: `src/loader.h`
- Modify: `bank-manifest.json`

**Prerequisite: Update bank-manifest.json first**

Add entry before writing the file:
```json
"src/loader.c": {"bank": 0, "reason": "NONBANKED VRAM loaders — only bank-0 code may call SWITCH_ROM"}
```

**Step 1: Write the failing test**

In `tests/test_loader.c` (new file):

```c
#include "unity.h"
#include "loader.h"

/* Mocks */
#include "mock_gbdk.h"   /* already exists in tests/mocks/ */

static int set_sprite_data_called = 0;
static int set_bkg_data_called = 0;
static int switch_rom_call_count = 0;
static uint8_t last_switch_rom_bank = 0;

/* Override the mock set_sprite_data */
void mock_set_sprite_data(uint8_t first, uint8_t nb_tiles, const uint8_t *data) {
    (void)first; (void)nb_tiles; (void)data;
    set_sprite_data_called = 1;
}

void mock_set_bkg_data(uint8_t first, uint8_t nb_tiles, const uint8_t *data) {
    (void)first; (void)nb_tiles; (void)data;
    set_bkg_data_called = 1;
}

void setUp(void) {
    set_sprite_data_called = 0;
    set_bkg_data_called = 0;
    switch_rom_call_count = 0;
}
void tearDown(void) {}

void test_load_player_tiles_calls_set_sprite_data(void) {
    load_player_tiles();
    TEST_ASSERT_EQUAL(1, set_sprite_data_called);
}

void test_load_track_tiles_calls_set_bkg_data(void) {
    load_track_tiles();
    TEST_ASSERT_EQUAL(1, set_bkg_data_called);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_load_player_tiles_calls_set_sprite_data);
    RUN_TEST(test_load_track_tiles_calls_set_bkg_data);
    return UNITY_END();
}
```

**Note:** Host tests mock out GBDK hardware calls. The test verifies the wrapper calls the right GBDK function, not that bank-switching works (hardware only). This is the correct scope for host tests.

Run:
```bash
make test 2>&1 | grep -E "test_loader|ERROR|FAIL"
```
Expected: compilation error (loader.h not found).

**Step 2: Write `src/loader.h`**

```c
#ifndef LOADER_H
#define LOADER_H

#include <gb/gb.h>
#include <stdint.h>

/* NONBANKED VRAM loaders — must be called from any bank.
 * These live in bank 0 so SWITCH_ROM is safe here. */
void load_player_tiles(void) NONBANKED;
void load_track_tiles(void) NONBANKED;
void load_track_start_pos(int16_t *x, int16_t *y) NONBANKED;

#endif /* LOADER_H */
```

**Step 3: Invoke bank-pre-write skill, then write `src/loader.c`**

bank-pre-write check: manifest has `loader.c` → bank 0 → no `#pragma bank`. SET_BANK is permitted. ✓

```c
/* src/loader.c — bank 0 (no #pragma bank). Only bank-0 code may call SWITCH_ROM. */
#include <gb/gb.h>
#include "loader.h"
#include "banking.h"
#include "player_sprite.h"
#include "track_tiles.h"
#include "track.h"

BANKREF_EXTERN(player_tile_data)
BANKREF_EXTERN(track_tile_data)
BANKREF_EXTERN(track_start_x)

void load_player_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(player_tile_data));
    set_sprite_data(0, player_tile_data_count, player_tile_data);
    SWITCH_ROM(saved);
}

void load_track_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(track_tile_data));
    set_bkg_data(0, track_tile_data_count, track_tile_data);
    SWITCH_ROM(saved);
}

void load_track_start_pos(int16_t *x, int16_t *y) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(track_start_x));
    *x = track_start_x;
    *y = track_start_y;
    SWITCH_ROM(saved);
}
```

**Step 4: Run tests to verify they pass**

```bash
make test 2>&1 | grep -E "test_loader|PASS|FAIL|OK"
```

**Step 5: Verify `player_sprite.h` and `track_tiles.h` exist and have the right externs**

```bash
grep -n "player_tile_data\|player_tile_data_count" src/player_sprite.h
grep -n "track_tile_data\|track_tile_data_count" src/track_tiles.h 2>/dev/null || echo "no track_tiles.h"
```

If `track_tiles.h` doesn't exist, check `track.h`:
```bash
grep -n "track_tile_data" src/track.h
```
Add externs to `track.h` if needed: `extern const uint8_t track_tile_data[]; extern const uint8_t track_tile_data_count;`

**Step 6: Commit**

```bash
git add bank-manifest.json src/loader.c src/loader.h
git commit -m "feat: add loader.c — NONBANKED bank-0 wrappers for VRAM asset loads"
```

---

### Task 1-D: Remove `SET_BANK` from `player.c`

**Files:**
- Modify: `src/player.c`

**Step 1: Invoke bank-pre-write skill**

`player.c` is already `#pragma bank 255` with manifest `bank: 255`. Check 3 now FAILS because it has `SET_BANK`. After this task, it will pass.

**Step 2: Replace SET_BANK blocks with loader calls**

In `player_init()`:

Current:
```c
{ SET_BANK(player_tile_data);
  set_sprite_data(0, 2, player_tile_data);
  RESTORE_BANK(); }
```
Replace with:
```c
load_player_tiles();
```

Current:
```c
{ SET_BANK(track_start_x);
  px = track_start_x;
  py = track_start_y;
  RESTORE_BANK(); }
```
Replace with:
```c
load_track_start_pos(&px, &py);
```

Also add `#include "loader.h"` to the includes, and remove `BANKREF_EXTERN(player_tile_data)` (no longer needed in this file since loader.c has it). Keep the `extern const uint8_t player_tile_data[]` declaration — no, actually that's defined in `player_sprite.h`; check if `player.h` or `player_sprite.h` already declares it.

**Step 3: Remove BANKREF_EXTERN from player.c if present**

Line 6: `BANKREF_EXTERN(player_tile_data)` — remove this (loader.c owns the BANKREF_EXTERN now).

**Step 4: Build to verify**

```bash
GBDK_HOME=/home/mathdaman/gbdk make 2>&1 | grep -E "player\.c|ERROR|error"
```
Expected: `player.c` compiles without error. (Build may still fail due to `track.c` — that's OK, continue to next task.)

**Step 5: Commit**

```bash
git add src/player.c
git commit -m "fix: remove SET_BANK from player_init — use loader.c wrappers instead"
```

---

### Task 1-E: Remove `SET_BANK` from `track.c`

**Files:**
- Modify: `src/track.c`

**Step 1: Replace SET_BANK block in `track_init()`**

Current:
```c
void track_init(void) BANKED {
    SET_BANK(track_tile_data);
    set_bkg_data(0, track_tile_data_count, track_tile_data);
    RESTORE_BANK();
    /* Tilemap loaded by camera_init() */
    SHOW_BKG;
}
```

Replace with:
```c
void track_init(void) BANKED {
    load_track_tiles();
    /* Tilemap loaded by camera_init() */
    SHOW_BKG;
}
```

Also add `#include "loader.h"` to the includes, and remove `BANKREF_EXTERN(track_tile_data)` (loader.c owns it now).

**Step 2: Build to verify**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: clean build, no errors.

**Step 3: Verify lint rule passes**

```bash
python3 tools/bank_check.py .
```
Expected: all files pass (no SET_BANK in banked files).

Verify AC3 from PRD:
```bash
grep -rn "SET_BANK\|SWITCH_ROM" src/ | grep -v "banking\.h\|loader\.c\|music\.c\|state_hub\.c\|state_overmap\.c\|main\.c"
```
Expected: empty output.

**Step 4: Commit**

```bash
git add src/track.c
git commit -m "fix: remove SET_BANK from track_init — use loader.c wrapper instead"
```

---

### Task 1-F: Audit `camera.c` for latent `track_map` access bug

**Files:**
- Possibly modify: `src/camera.c` or `src/track.c`

**Step 1: Read `camera.c` and check for direct `track_map[]` access**

```bash
grep -n "track_map" src/camera.c
```

Current code (`stream_row` function, line 19):
```c
row_buf[tx] = track_map[(uint16_t)world_ty * MAP_TILES_W + tx];
```

`camera.c` is `#pragma bank 255` (autobank) and accesses `track_map[]` directly without a bank switch. `track_map.c` is also `#pragma bank 255`. They may or may not share a bank after autobank migration.

**Step 2: Determine fix**

Per PRD P1-R7 Option A: add a BANKED accessor in `track.c` and use it in `camera.c`.

Add to `src/track.h`:
```c
/* Returns the raw tile index at world tile position (tx, ty). */
uint8_t track_get_raw_tile(uint8_t tx, uint8_t ty) BANKED;
```

Add to `src/track.c` (no SET_BANK needed — track.c and track_map.c will be in the same autobank):
```c
uint8_t track_get_raw_tile(uint8_t tx, uint8_t ty) BANKED {
    if (tx >= MAP_TILES_W || ty >= MAP_TILES_H) return 0u;
    return track_map[(uint16_t)ty * MAP_TILES_W + tx];
}
```

Update `camera.c` `stream_row()`:
```c
static void stream_row(uint8_t world_ty) {
    static uint8_t row_buf[MAP_TILES_W];
    uint8_t tx;
    uint8_t vram_y = world_ty & 31u;

    for (tx = 0u; tx < MAP_TILES_W; tx++) {
        row_buf[tx] = track_get_raw_tile(tx, world_ty);
    }
    set_bkg_tiles(0u, vram_y, MAP_TILES_W, 1u, row_buf);
}
```

**Note:** `track_get_raw_tile()` is BANKED and called from `camera.c` which is also `#pragma bank 255`. GBDK's BANKED call trampoline handles cross-bank dispatch — it saves the current bank, switches to the callee's bank, runs, and restores. This is the safe pattern for cross-bank calls.

**Step 3: Build to verify**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: clean build.

**Step 4: Add a comment to `camera.c` documenting the constraint**

At the top of `stream_row()`:
```c
/* track_get_raw_tile() is BANKED — the trampoline handles bank switching safely.
 * Direct access to track_map[] is forbidden here (camera.c and track_map.c may
 * be in different autobanks). */
```

**Step 5: Commit**

```bash
git add src/camera.c src/track.c src/track.h
git commit -m "fix: camera.c — use track_get_raw_tile() BANKED trampoline instead of direct track_map access"
```

---

### Task 1-G: Refactor `state_manager.c` — bank 0, `invoke()` dispatch

**Files:**
- Modify: `src/state_manager.h`
- Modify: `src/state_manager.c`
- Modify: `bank-manifest.json`

**Step 1: Update bank-manifest.json**

Change:
```json
"src/state_manager.c": {"bank": 1, "reason": "state dispatch — pinned bank 1, all state callbacks must match"},
```
To:
```json
"src/state_manager.c": {"bank": 0, "reason": "state dispatch uses invoke(); must call SWITCH_ROM from bank 0"},
```

**Step 2: Update `src/state_manager.h` — add `bank` field to State struct**

```c
#ifndef STATE_MANAGER_H
#define STATE_MANAGER_H

#include <gb/gb.h>
#include <stdint.h>

typedef struct {
    uint8_t bank;
    void (*enter)(void);   /* plain, NOT BANKED — invoke() handles bank switching */
    void (*update)(void);
    void (*exit)(void);
} State;

void state_manager_init(void);
void state_manager_update(void);

void state_push(const State *s);
void state_pop(void);
void state_replace(const State *s);

#endif
```

Note: Functions are no longer `BANKED` (state_manager.c is bank 0).

**Step 3: Invoke bank-pre-write skill for state_manager.c**

Manifest: bank 0 → no `#pragma bank`. No SET_BANK calls needed here (invoke() uses SWITCH_ROM directly). ✓

**Step 4: Rewrite `src/state_manager.c`**

```c
/* state_manager.c — bank 0 (no #pragma bank). Uses invoke() to dispatch
 * state callbacks; SWITCH_ROM is safe from bank-0 code. */
#include <gb/gb.h>
#include "state_manager.h"

#define STACK_MAX 2

static const State *stack[STACK_MAX];
static uint8_t depth = 0;

static void invoke(void (*fn)(void), uint8_t bank) {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(bank);
    fn();
    SWITCH_ROM(saved);
}

void state_manager_init(void) {
    depth = 0;
}

void state_manager_update(void) {
    if (depth == 0) return;
    invoke(stack[depth - 1]->update, stack[depth - 1]->bank);
}

void state_push(const State *s) {
    if (depth >= STACK_MAX) return;
    stack[depth++] = s;
    invoke(s->enter, s->bank);
}

void state_pop(void) {
    if (depth == 0) return;
    invoke(stack[depth - 1]->exit, stack[depth - 1]->bank);
    depth--;
    if (depth > 0) {
        invoke(stack[depth - 1]->enter, stack[depth - 1]->bank);
    }
}

void state_replace(const State *s) {
    if (depth == 0) {
        stack[depth++] = s;
        invoke(s->enter, s->bank);
        return;
    }
    invoke(stack[depth - 1]->exit, stack[depth - 1]->bank);
    stack[depth - 1] = s;
    invoke(s->enter, s->bank);
}
```

**Step 5: Build to see expected compilation errors**

```bash
GBDK_HOME=/home/mathdaman/gbdk make 2>&1 | head -30
```
Expected: errors in `state_playing.c`, `state_title.c`, `state_hub.c`, `state_overmap.c` because they still export `const State` without the `bank` field, and still have `#pragma bank 1` (for state_playing and state_title). This is expected — fixed in the next tasks.

**Step 6: Commit the manager changes**

```bash
git add bank-manifest.json src/state_manager.h src/state_manager.c
git commit -m "refactor: state_manager.c — bank 0, invoke() dispatch, State struct +bank field"
```

---

### Task 1-H: Update state callback files — playing, title, hub, overmap

**Files:**
- Modify: `src/state_playing.c`, `src/state_playing.h`
- Modify: `src/state_title.c`, `src/state_title.h`
- Modify: `src/state_hub.c`, `src/state_hub.h`
- Modify: `src/state_overmap.c`, `src/state_overmap.h`
- Modify: `bank-manifest.json`

**Step 1: Update bank-manifest.json**

```json
"src/state_playing.c":   {"bank": 255, "reason": "autobank — state callback; invoke() in state_manager.c handles bank switching"},
"src/state_title.c":     {"bank": 255, "reason": "autobank — state callback; invoke() in state_manager.c handles bank switching"},
```

(state_hub.c and state_overmap.c remain bank 0 — no change needed.)

**Step 2: Update `src/state_playing.c`**

Change `#pragma bank 1` → `#pragma bank 255`.

Add `BANKREF(state_playing)` after the includes.

Change the State export to include the bank field:
```c
BANKREF(state_playing)
const State state_playing = { BANK(state_playing), enter, update, sp_exit };
```

**Step 3: Update `src/state_title.c`**

Change `#pragma bank 1` → `#pragma bank 255`.

Add `BANKREF(state_title)` after the includes.

Change the State export:
```c
BANKREF(state_title)
const State state_title = { BANK(state_title), enter, update, st_exit };
```

**Step 4: Update `src/state_hub.c` (bank 0 — no pragma change)**

Add `BANKREF(state_hub)` (bank 0 files can use BANKREF; BANK(state_hub) = 0, SWITCH_ROM(0) is a no-op).

Change State export:
```c
BANKREF(state_hub)
const State state_hub = { BANK(state_hub), enter, update, hub_exit };
```

**Step 5: Update `src/state_overmap.c` (bank 0 — no pragma change)**

Add `BANKREF(state_overmap)`.

Change State export:
```c
BANKREF(state_overmap)
const State state_overmap = { BANK(state_overmap), enter, update, om_exit };
```

**Step 6: Update header files**

In each `.h` file, update the `extern const State state_X;` declarations (no API change needed since the State struct fields changed only internally).

Check `state_playing.h`:
```c
extern const State state_playing;
```
These declarations are fine as-is (the struct change is transparent to callers using const State *).

**Step 7: Build to verify**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: clean build.

**Step 8: Run all tests**

```bash
make test && make test-tools
```
Expected: all pass.

**Step 9: Verify AC3**

```bash
grep -rn "SET_BANK\|SWITCH_ROM" src/ | grep -v "banking\.h\|loader\.c\|music\.c\|state_hub\.c\|state_overmap\.c\|main\.c"
```
Expected: empty.

**Step 10: Commit**

```bash
git add bank-manifest.json src/state_playing.c src/state_playing.h \
        src/state_title.c src/state_title.h \
        src/state_hub.c src/state_hub.h \
        src/state_overmap.c src/state_overmap.h
git commit -m "refactor: state callbacks — autobank 255 for playing/title, BANKREF exports, bank field in State"
```

---

### Task 1-I: Unpin NPC portrait files

**Files:**
- Modify: `bank-manifest.json`
- Modify: `Makefile`
- Regenerate: `src/npc_mechanic_portrait.c`, `src/npc_trader_portrait.c`, `src/npc_drifter_portrait.c`

**Step 1: Update bank-manifest.json**

```json
"src/npc_mechanic_portrait.c": {"bank": 255, "reason": "autobank — loader.c handles BANK(sym) switching"},
"src/npc_trader_portrait.c":   {"bank": 255, "reason": "autobank — loader.c handles BANK(sym) switching"},
"src/npc_drifter_portrait.c":  {"bank": 255, "reason": "autobank — loader.c handles BANK(sym) switching"},
```

**Step 2: Update Makefile portrait rules**

Change `--bank 2` → `--bank 255` in all three portrait rules. Also update the comment above them to remove the old rationale about bank-1 overflow.

New comment:
```makefile
# NPC portraits use --bank 255 (autobank). state_hub.c (bank 0) calls SET_BANK to
# load portrait tiles into VRAM. Bank-0 code may freely call SWITCH_ROM.
```

**Step 3: Regenerate portrait files**

```bash
python3 tools/png_to_tiles.py --bank 255 assets/sprites/npc_mechanic.png src/npc_mechanic_portrait.c npc_mechanic_portrait
python3 tools/png_to_tiles.py --bank 255 assets/sprites/npc_trader.png src/npc_trader_portrait.c npc_trader_portrait
python3 tools/png_to_tiles.py --bank 255 assets/sprites/npc_drifter.png src/npc_drifter_portrait.c npc_drifter_portrait
```

**Step 4: Verify BANKREF is present in generated files**

```bash
grep -n "BANKREF" src/npc_mechanic_portrait.c src/npc_trader_portrait.c src/npc_drifter_portrait.c
```
Expected: each file contains `BANKREF(npc_<name>_portrait)`.

**Step 5: Run bank_check to verify manifest matches**

```bash
python3 tools/bank_check.py .
```
Expected: all pass.

**Step 6: Build to verify**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: clean build.

**Step 7: Commit**

```bash
git add bank-manifest.json Makefile \
        src/npc_mechanic_portrait.c \
        src/npc_trader_portrait.c \
        src/npc_drifter_portrait.c
git commit -m "fix: unpin NPC portraits to bank 255 (autobank) — loader.c handles bank switching"
```

---

### Task 1-J: Final verification — all acceptance criteria

**Step 1: AC1 — Clean build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero warnings/errors.

**Step 2: AC2 — bank-post-build passes**

Invoke `bank-post-build` skill (runs `make bank-post-build`).
Expected: exit 0, no bank overflows.

**Step 3: AC3 — No SET_BANK/SWITCH_ROM in banked files**

```bash
grep -rn "SET_BANK\|SWITCH_ROM" src/ | grep -v "banking\.h\|loader\.c\|music\.c\|state_hub\.c\|state_overmap\.c\|main\.c"
```
Expected: empty output.

**Step 4: AC4 — All tests pass**

```bash
make test && make test-tools
```
Expected: all pass.

**Step 5: AC6 — No manual SET_BANK in any file with #pragma bank (all banks)**

```bash
python3 bank_check.py
```
Expected: all pass. (AC6 was revised: explicit bank pins like `#pragma bank 2` are correct for heavy data files — the invariant is no SET_BANK in banked code, not no explicit pins.)

**Step 6: AC7 — bank_check rejects SET_BANK in banked file**

```bash
python3 -m unittest tests.test_bank_check.TestBankCheck.test_set_bank_in_banked_file_is_error -v
```
Expected: PASS.

**Step 7: AC8 — png_to_tiles.py --bank 255 emits BANKREF**

```bash
python3 -m unittest tests.test_png_to_tiles.TestPngToC.test_bank_ref_uses_bankref_for_autobank -v
```
Expected: PASS.

**Step 8: AC9 — png_to_tiles.py --bank 2 still uses volatile __at**

```bash
python3 -m unittest tests.test_png_to_tiles.TestPngToC.test_bank_ref_uses_volatile_at_explicit_bank -v
```
Expected: PASS.

**Step 9: AC10 — Phase 0 merged first**

Phase 0 was merged before Phase 1 code was written. ✓ (architectural requirement, verified by process).

**Step 10: Run gb-memory-validator agent**

Invoke the `gb-memory-validator` agent to confirm WRAM, VRAM, and OAM budgets are within limits.

**Step 11: Smoketest in Emulicious**

```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb &
```

Verify manually:
- Title screen appears with "JUNK RUNNER" text and "Press START"
- START → overmap navigation works
- Enter race destination → race plays, player moves
- NPC dialog + portrait render correctly in hub
- Music plays throughout

---

### Task 1-K: Update README.md if needed, then push and create PR

**Step 1: Check if README needs updating**

This migration is internal (no user-visible behavior changes). Skip README update.

**Step 2: Push branch**

```bash
git push -u origin worktree-feat/autobank-migration
```

**Step 3: Create PR**

```bash
gh pr create \
  --title "feat: full autobank migration — eliminate manual bank pins and SET_BANK violations" \
  --body "$(cat <<'EOF'
## Summary
- Phase 0: Updated bank-pre-write skill, sprite-expert skill, gbdk-expert agent, CLAUDE.md, and memory files to reflect new architecture invariant (only bank-0 files may call SET_BANK/SWITCH_ROM)
- Phase 1: Added loader.c NONBANKED wrappers, invoke() state dispatch in bank-0 state_manager, unpinned portrait files to autobank 255, fixed png_to_tiles.py to emit BANKREF for autobank files, added SET_BANK-in-banked lint rule to bank_check.py

## Test plan
- [ ] `make test` passes (host-side unit tests)
- [ ] `make test-tools` passes (Python tool tests)
- [ ] `make bank-post-build` exits 0, no bank overflows
- [ ] `grep SET_BANK/SWITCH_ROM` returns empty for banked files (AC3)
- [ ] Smoketest in Emulicious: title, overmap, race, NPC dialog + portrait, music all correct

Closes #123

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Notes on Testing Strategy

**Host tests (`make test`):** Run with gcc + mocked GBDK headers. Test business logic and tool correctness. Do NOT test hardware-specific behavior (bank switching, VRAM writes) — those require emulator.

**Tool tests (`make test-tools`):** Test Python scripts (png_to_tiles.py, bank_check.py, tmx_to_c.py). Fully host-runnable.

**The lint rule in bank_check.py** will catch regressions at build time — any future file that accidentally adds SET_BANK in a banked context will fail the build before it can be merged.

**Why invoke() over FAR_PTR:** FAR_PTR requires `MAKE_FAR_PTR()` at registration and `FAR_CALL()` at every dispatch site. invoke() achieves the same with a single helper, plain function pointers (avoids SDCC double-dereference bug for BANKED struct fields), and is host-test friendly (bank=0 is a no-op invoke).
