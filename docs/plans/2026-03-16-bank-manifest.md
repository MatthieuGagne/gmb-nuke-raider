# Bank Manifest & Gate Skills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate recurring ROM banking bugs by replacing reactive debugging with proactive prevention: a `bank-manifest.json` as single source of truth, two gate skills (bank-pre-write, bank-post-build), a Makefile-level checker, and consolidated agents.

**Architecture:** A JSON manifest declares the intended bank for every `src/*.c` file. `tools/bank_check.py` validates pragmas against the manifest at build time (Makefile dependency). Two lean skills (<400 tokens each) replace the ~3000-token combination of rom-banking + gbdk-expert banking sections + gb-memory-validator ROM checks.

**Tech Stack:** Python 3, JSON, Make, GBDK `romusage`, Makefile, Claude skills/agents (Markdown).

**GitHub issue:** Closes #111

---

## Bank Assignment Reference

The current `#pragma bank` state for every `src/*.c` file (verified from codebase):

| File | Bank | Reason |
|------|------|--------|
| `camera.c` | 255 | autobank |
| `dialog.c` | 255 | autobank |
| `dialog_arrow_sprite.c` | 255 | autobank |
| `dialog_data.c` | 255 | autobank |
| `hub_data.c` | 0 | bank-0 data, always mapped; no pragma |
| `hud.c` | 255 | autobank |
| `main.c` | 0 | game entry, VBL handling; no pragma |
| `music.c` | 0 | VBL ISR music_tick must be in HOME bank; no pragma |
| `music_data.c` | 255 | autobank |
| `npc_drifter_portrait.c` | 2 | pinned to avoid competing with state code in bank 1 |
| `npc_mechanic_portrait.c` | 2 | same |
| `npc_trader_portrait.c` | 2 | same |
| `overmap_map.c` | 255 | autobank |
| `overmap_tiles.c` | 255 | autobank |
| `player.c` | 255 | autobank |
| `player_sprite.c` | 255 | autobank |
| `sprite_pool.c` | 255 | autobank |
| `state_hub.c` | 0 | makes SET_BANK calls, must be HOME bank; no pragma |
| `state_manager.c` | 1 | state dispatch — must always be bank 1 |
| `state_overmap.c` | 0 | makes SET_BANK calls, HOME bank; no pragma |
| `state_playing.c` | 1 | state callback — must be bank 1 with state_manager |
| `state_title.c` | 1 | state callback — must be bank 1 with state_manager |
| `track.c` | 255 | autobank |
| `track_map.c` | 255 | autobank |
| `track_tiles.c` | 255 | autobank |

**`#pragma bank` convention:**
- Bank 0 → **no** `#pragma bank` line (file runs in HOME bank, always mapped)
- Bank 1 → `#pragma bank 1`
- Bank 2 → `#pragma bank 2`
- Bank 255 → `#pragma bank 255` (autobank)

---

### Task 1: Create `bank-manifest.json`

No test needed — `bank_check.py` (Task 2) validates it.

**Files:**
- Create: `bank-manifest.json` (repo root)

**Step 1: Create the manifest**

```json
{
  "src/camera.c":                {"bank": 255, "reason": "autobank"},
  "src/dialog.c":                {"bank": 255, "reason": "autobank"},
  "src/dialog_arrow_sprite.c":   {"bank": 255, "reason": "autobank"},
  "src/dialog_data.c":           {"bank": 255, "reason": "autobank"},
  "src/hub_data.c":              {"bank": 0,   "reason": "bank-0 data, always mapped — no #pragma bank"},
  "src/hud.c":                   {"bank": 255, "reason": "autobank"},
  "src/main.c":                  {"bank": 0,   "reason": "game entry / VBL handling — no #pragma bank"},
  "src/music.c":                 {"bank": 0,   "reason": "VBL ISR music_tick must be in HOME bank — no #pragma bank"},
  "src/music_data.c":            {"bank": 255, "reason": "autobank"},
  "src/npc_drifter_portrait.c":  {"bank": 2,   "reason": "pinned: must not compete with state code for bank 1"},
  "src/npc_mechanic_portrait.c": {"bank": 2,   "reason": "pinned: must not compete with state code for bank 1"},
  "src/npc_trader_portrait.c":   {"bank": 2,   "reason": "pinned: must not compete with state code for bank 1"},
  "src/overmap_map.c":           {"bank": 255, "reason": "autobank"},
  "src/overmap_tiles.c":         {"bank": 255, "reason": "autobank"},
  "src/player.c":                {"bank": 255, "reason": "autobank"},
  "src/player_sprite.c":         {"bank": 255, "reason": "autobank"},
  "src/sprite_pool.c":           {"bank": 255, "reason": "autobank"},
  "src/state_hub.c":             {"bank": 0,   "reason": "calls SET_BANK — must be HOME bank; no #pragma bank"},
  "src/state_manager.c":         {"bank": 1,   "reason": "state dispatch — pinned bank 1, all state callbacks must match"},
  "src/state_overmap.c":         {"bank": 0,   "reason": "calls SET_BANK — must be HOME bank; no #pragma bank"},
  "src/state_playing.c":         {"bank": 1,   "reason": "state callback — must be bank 1 with state_manager"},
  "src/state_title.c":           {"bank": 1,   "reason": "state callback — must be bank 1 with state_manager"},
  "src/track.c":                 {"bank": 255, "reason": "autobank"},
  "src/track_map.c":             {"bank": 255, "reason": "autobank"},
  "src/track_tiles.c":           {"bank": 255, "reason": "autobank"}
}
```

**Step 2: Commit**

```bash
git add bank-manifest.json
git commit -m "feat: add bank-manifest.json — single source of truth for src/*.c bank assignments"
```

---

### Task 2: Create `tools/bank_check.py` (TDD)

**Files:**
- Create: `tools/bank_check.py`
- Create: `tests/test_bank_check.py`

**Step 1: Write failing tests**

Create `tests/test_bank_check.py`:

```python
"""Tests for tools/bank_check.py"""
import json
import os
import sys
import tempfile
import unittest

# Allow importing from tools/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import bank_check


class TestBankCheck(unittest.TestCase):

    def _write_manifest(self, d, entries):
        path = os.path.join(d, 'bank-manifest.json')
        with open(path, 'w') as f:
            json.dump(entries, f)
        return path

    def _write_c(self, d, name, lines):
        path = os.path.join(d, 'src', name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        return path

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_bank255_pragma_matches(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/foo.c': {'bank': 255, 'reason': 'autobank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'foo.c', ['#pragma bank 255', '#include <gb/gb.h>'])
            errors = bank_check.check(d)
        self.assertEqual(errors, [])

    def test_bank1_pragma_matches(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/state_manager.c': {'bank': 1, 'reason': 'pinned'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'state_manager.c', ['#pragma bank 1', '#include <gb/gb.h>'])
            errors = bank_check.check(d)
        self.assertEqual(errors, [])

    def test_bank0_no_pragma(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/main.c': {'bank': 0, 'reason': 'HOME bank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'main.c', ['#include <gb/gb.h>', 'void main() {}'])
            errors = bank_check.check(d)
        self.assertEqual(errors, [])

    # ── Error: wrong pragma ───────────────────────────────────────────────────

    def test_bank255_wrong_pragma(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/foo.c': {'bank': 255, 'reason': 'autobank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'foo.c', ['#pragma bank 1', '#include <gb/gb.h>'])
            errors = bank_check.check(d)
        self.assertEqual(len(errors), 1)
        self.assertIn('foo.c', errors[0])
        self.assertIn('255', errors[0])

    def test_bank0_has_pragma(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/main.c': {'bank': 0, 'reason': 'HOME bank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'main.c', ['#pragma bank 255', '#include <gb/gb.h>'])
            errors = bank_check.check(d)
        self.assertEqual(len(errors), 1)
        self.assertIn('main.c', errors[0])

    # ── Error: file not in manifest ────────────────────────────────────────────

    def test_file_missing_from_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {}
            self._write_manifest(d, manifest)
            self._write_c(d, 'new_module.c', ['#pragma bank 255'])
            errors = bank_check.check(d)
        self.assertEqual(len(errors), 1)
        self.assertIn('new_module.c', errors[0])
        self.assertIn('manifest', errors[0].lower())

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_pragma_on_line_2_still_found(self):
        """Pragma may appear on line 2 (after a comment)."""
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/foo.c': {'bank': 255, 'reason': 'autobank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'foo.c', ['/* comment */', '#pragma bank 255', '#include <gb/gb.h>'])
            errors = bank_check.check(d)
        self.assertEqual(errors, [])

    def test_empty_src_dir_no_errors(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {}
            self._write_manifest(d, manifest)
            os.makedirs(os.path.join(d, 'src'))
            errors = bank_check.check(d)
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_bank_check.py -v 2>&1 | head -20
# OR if pytest not available:
python3 -m unittest tests.test_bank_check -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'bank_check'`

**Step 3: Implement `tools/bank_check.py`**

```python
#!/usr/bin/env python3
"""
bank_check.py — validates #pragma bank in src/*.c against bank-manifest.json.
Exits 0 on success, 1 if any mismatches found.

Usage:
    python3 tools/bank_check.py [repo_root]
    or imported as a module: bank_check.check(repo_root) -> list[str]
"""
import glob
import json
import os
import sys


def check(repo_root='.'):
    """Return list of error strings. Empty list means all clear."""
    manifest_path = os.path.join(repo_root, 'bank-manifest.json')
    with open(manifest_path) as f:
        manifest = json.load(f)

    errors = []
    src_files = glob.glob(os.path.join(repo_root, 'src', '*.c'))

    for abs_path in sorted(src_files):
        rel_path = 'src/' + os.path.basename(abs_path)
        if rel_path not in manifest:
            errors.append(
                f"ERROR: {rel_path} is not in bank-manifest.json — "
                f"add an entry before writing this file"
            )
            continue

        expected_bank = manifest[rel_path]['bank']

        with open(abs_path) as f:
            first_lines = [f.readline().rstrip() for _ in range(5)]

        pragma_lines = [l for l in first_lines if l.startswith('#pragma bank')]

        if expected_bank == 0:
            # Bank-0 files must NOT have #pragma bank
            if pragma_lines:
                errors.append(
                    f"ERROR: {rel_path} has '{pragma_lines[0]}' but manifest says bank 0 "
                    f"(bank-0 files must omit #pragma bank entirely)"
                )
        else:
            expected_pragma = f'#pragma bank {expected_bank}'
            if not any(l == expected_pragma for l in pragma_lines):
                found = pragma_lines[0] if pragma_lines else '(none in first 5 lines)'
                errors.append(
                    f"ERROR: {rel_path} pragma mismatch — "
                    f"manifest expects '{expected_pragma}', found: {found}"
                )

    return errors


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    errors = check(repo_root)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    print(f"bank_check: all {len(list(glob.glob(os.path.join(repo_root, 'src', '*.c'))))} src/*.c files match manifest")
    sys.exit(0)


if __name__ == '__main__':
    main()
```

**Step 4: Run tests to verify they pass**

```bash
python3 -m unittest tests.test_bank_check -v
```

Expected: All 8 tests PASS

**Step 5: Manually verify on real codebase**

```bash
python3 tools/bank_check.py .
```

Expected: `bank_check: all 25 src/*.c files match manifest`

**Step 6: Commit**

```bash
git add tools/bank_check.py tests/test_bank_check.py
git commit -m "feat: add bank_check.py — validates #pragma bank against bank-manifest.json"
```

---

### Task 3: Wire `bank_check.py` into the Makefile

**Files:**
- Modify: `Makefile`

**Step 1: Read current Makefile top section** (already done above — just the `all` target and `$(TARGET)` rule)

**Step 2: Add bank-check target and wire as dependency**

In `Makefile`, add a `bank-check` phony target and make `$(TARGET)` depend on it. Insert immediately after the `.PHONY` line:

Find this in the Makefile:
```makefile
.PHONY: all clean test test-tools export-sprites
```

Replace with:
```makefile
.PHONY: all clean test test-tools export-sprites bank-check
```

Then find the `all: $(TARGET)` line and the `$(TARGET): $(OBJS) | build` rule and add `bank-check` as a dependency of `all`:

Find:
```makefile
all: $(TARGET)
```

Replace with:
```makefile
all: bank-check $(TARGET)
```

Then add the `bank-check` recipe at the end of the file (before `clean:`):

```makefile
bank-check:
	python3 tools/bank_check.py .
```

**Step 3: Verify build still works**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: `bank_check: all 25 src/*.c files match manifest` printed, then normal build output, ROM produced at `build/nuke-raider.gb`

**Step 4: Verify bank_check blocks wrong pragma**

Temporarily corrupt a file to test the gate works:
```bash
# Temporarily break it
sed -i 's/#pragma bank 255/#pragma bank 1/' src/camera.c
GBDK_HOME=/home/mathdaman/gbdk make 2>&1 | head -5
# Expected: ERROR: src/camera.c pragma mismatch...
# Expected: make exits non-zero
git checkout src/camera.c  # restore
```

**Step 5: Commit**

```bash
git add Makefile
git commit -m "feat: wire bank_check.py into Makefile — build fails on pragma/manifest mismatch"
```

---

### Task 4: Create `bank-pre-write` skill

No test — this is a skill document consumed by Claude.

**Files:**
- Create: `.claude/skills/bank-pre-write/SKILL.md`

**Step 1: Create the skill directory and file**

```bash
mkdir -p .claude/skills/bank-pre-write
```

Content for `.claude/skills/bank-pre-write/SKILL.md`:

```markdown
---
name: bank-pre-write
description: Hard gate — invoke before writing any src/*.c or src/*.h file. Validates bank manifest, pragma, and SET_BANK safety.
---

# Bank Pre-Write Gate

**STOP.** Before writing or editing any `src/*.c` or `src/*.h` file, run every check below. Block writing if any check fails.

## Check 1 — Manifest entry exists

Read `bank-manifest.json` at the repo root.

- If the file you are about to write is NOT in the manifest → **BLOCK**:
  > "Add an entry to `bank-manifest.json` for `src/<file>.c` before writing it. Specify bank number (255 for autobank, 1 for state code, 2 for portraits, 0 for HOME bank code) and reason."

- If creating a new `state_*.c` file → manifest bank **must** be 1 (or 0 if it calls SET_BANK).
- If creating a new `npc_*_portrait.c` file → manifest bank **must** be 2.

## Check 2 — Pragma matches manifest

Look up the file's expected bank in `bank-manifest.json`.

| Manifest bank | Required in first 5 lines of `.c` file |
|---------------|----------------------------------------|
| 0             | No `#pragma bank` line at all |
| 1             | `#pragma bank 1` |
| 2             | `#pragma bank 2` |
| 255           | `#pragma bank 255` |

If the pragma you are about to write doesn't match → **BLOCK and correct it before writing.**

## Check 3 — No `SET_BANK` inside banked code

If the file's manifest bank is **not 0** (i.e., it lives in the switchable window 0x4000–0x7FFF):

- **BLOCK** any `SET_BANK(...)` call inside that file.
  > Reason: calling SET_BANK from banked code switches the window away from the running function → crash.
  > Fix: move the SET_BANK call into a bank-0 caller, or move the calling function to a bank-0 file.

Bank-0 files (`main.c`, `music.c`, `hub_data.c`, `state_hub.c`, `state_overmap.c`) may freely call `SET_BANK`.

## Check 4 — No `BANKED` on static functions or bank-0 functions

- `static` functions must NOT be `BANKED` — they cannot be called cross-bank anyway.
- Bank-0 functions must NOT be `BANKED` — they're always mapped; the keyword generates useless trampoline overhead.
- Function pointer fields in structs must NOT be `BANKED` — SDCC generates broken double-dereference code. Use plain `void (*fn)(void)`.

## Check 5 — Makefile `--bank` flags consistent

NPC portrait files are pinned via `--bank 2` in the Makefile `png_to_tiles.py` invocation.

If adding a new generated file that must be pinned, ensure the Makefile passes `--bank N` to `png_to_tiles.py` and the manifest entry matches.

## If all checks pass

Proceed with writing the file. Announce: "bank-pre-write: all checks passed for `src/<file>.c` (bank N)."
```

**Step 2: Commit**

```bash
git add .claude/skills/bank-pre-write/SKILL.md
git commit -m "feat: add bank-pre-write skill — hard gate before writing src/*.c files"
```

---

### Task 5: Create `bank-post-build` skill

**Files:**
- Create: `.claude/skills/bank-post-build/SKILL.md`

**Step 1: Create the skill**

```bash
mkdir -p .claude/skills/bank-post-build
```

Content for `.claude/skills/bank-post-build/SKILL.md`:

```markdown
---
name: bank-post-build
description: Hard gate — invoke after a successful build, before smoketest. Validates .map symbol placements against manifest and checks ROM bank budgets.
---

# Bank Post-Build Gate

Run after `GBDK_HOME=/home/mathdaman/gbdk make` succeeds. Block proceeding to smoketest if any check fails.

## Step 1 — Run romusage

```sh
/home/mathdaman/gbdk/bin/romusage build/nuke-raider.gb -a
```

### Budget thresholds

| Bank | WARN | FAIL |
|------|------|------|
| Bank 1 | >90% | >100% |
| All others | >80% | >100% |

If any bank FAILs → **BLOCK.** Tell user:
> "Bank N is full. Fix: bump `-Wm-ya` to the next power of 2 in the Makefile (e.g. `-Wm-ya16` → `-Wm-ya32`)."

If bank 1 WARNs (>90%) → flag prominently:
> "Bank 1 is at X% — state code is at risk of overflowing. Consider bumping `-Wm-ya` now."

## Step 2 — Check state code stays in bank 1

```sh
grep "_state_" build/nuke-raider.map | grep -v "^;" | grep -v " 014[0-9A-Fa-f]\{3\} "
```

Symbols matching `_state_*` that appear at addresses **outside** `0x14000–0x17FFF` (bank 1 range) indicate overflow.

If any `_state_` symbol appears at `0x024xxx` or higher → **BLOCK:**
> "State code overflowed bank 1 — blank screen crash at boot guaranteed. Bump `-Wm-ya` to next power of 2."

## Step 3 — Verify `__bank_` symbols match manifest

```sh
grep "__bank_" build/nuke-raider.map | grep -v "^;"
```

For each `__bank_<symbol>` entry, the numeric value should match the manifest's bank for the file containing that symbol.

If a `__bank_` value is wrong → flag to user. Common cause: BANKREF placed in a different file than the data it references (was the root cause of PR #107).

## Step 4 — Check `-Wm-ya` declares enough banks

```sh
grep "\-Wm-ya" Makefile
/home/mathdaman/gbdk/bin/romusage build/nuke-raider.gb -a | grep "ROM Bank"
```

The highest bank number in use must be < the value declared with `-Wm-ya`. If banks are present beyond the declared count → **BLOCK.**

## Output format

```
=== Bank Post-Build Report ===
Bank 0: X / 16384 bytes (Y%)  [PASS/WARN/FAIL]
Bank 1: X / 16384 bytes (Y%)  [PASS/WARN/FAIL]
...
State symbols: [OK — all in bank 1] or [FAIL — N symbols outside bank 1]
__bank_ symbols: [OK] or [FAIL — list mismatches]
-Wm-ya capacity: [OK — Ya banks declared, M highest in use] or [FAIL]

[PASS / WARN / FAIL — overall]
```

If all checks pass: "bank-post-build: all checks passed — safe to proceed to smoketest."
```

**Step 2: Commit**

```bash
git add .claude/skills/bank-post-build/SKILL.md
git commit -m "feat: add bank-post-build skill — hard gate after build, before smoketest"
```

---

### Task 6: Refactor `gb-memory-validator` agent — remove ROM bank checks

**Files:**
- Modify: `.claude/agents/gb-memory-validator.md`

The agent currently checks 4 budgets: ROM per-bank, WRAM, VRAM, OAM.
ROM per-bank checking moves to `bank-post-build`. The agent keeps WRAM, VRAM, OAM only.

**Step 1: Edit the agent**

Replace the full content of `.claude/agents/gb-memory-validator.md` with:

```markdown
---
name: gb-memory-validator
description: Validates WRAM, VRAM, and OAM budgets after a successful build. ROM bank budget is checked by the bank-post-build skill. Reports PASS/WARN/FAIL — no auto-fix.
color: green
---

You are a Game Boy memory budget validator for the Junk Runner project.

Run after a successful build. Check WRAM, VRAM, and OAM budgets. **Do not check ROM bank budgets** — those are handled by the `bank-post-build` skill. **Do not edit any source files or the Makefile** — your job is to report, not fix.

When invoked, the worktree path may be provided in the prompt. Use it as the base directory for all file paths. If no worktree path is given, use the current working directory.

---

## Thresholds

- PASS — under 80% used
- WARN — 80%–99% used
- FAIL — at or over budget (100%)

---

## Check 1 — WRAM (budget: 8,192 bytes)

```sh
/home/mathdaman/gbdk/bin/romusage build/nuke-raider.gb -B
```

Parse `_RAM` / WRAM usage. If not directly reported, fall back:
```sh
/home/mathdaman/gbdk/bin/romusage build/nuke-raider.gb -a
```
Sum HOME/BSS/DATA sections in WRAM range (C000–DFFF).

**If FAIL:** Report to user. Do NOT auto-fix. State: "WRAM overrun requires architecture changes — manual intervention required."

---

## Check 2 — VRAM Tiles (budget: 384 tiles, 2 CGB banks × 192)

```sh
ls src/*_tiles.h src/*_map.h 2>/dev/null
```

For each header, count tiles: N bytes of tile data ÷ 16 = tile count. Search `uint8_t.*\[\]` definitions or `_TILE_COUNT` constants.

**If FAIL:** Report to user. Do NOT auto-fix. State: "VRAM overrun requires asset reduction — manual intervention required."

---

## Check 3 — OAM Slots (budget: 40 sprites)

```sh
grep -r "MAX_.*SPRITE\|MAX_.*OAM\|OAM_COUNT\|SPRITE_COUNT\|MAX_ENEMIES\|MAX_CARS\|MAX_PROJECTILES" src/config.h src/*.h 2>/dev/null
```

Sum all pool sizes consuming OAM slots (player: 2, enemy/car pool, projectile pool, HUD sprites).

**If FAIL:** Report to user. Do NOT auto-fix. State: "OAM overrun requires pool size reduction in config.h — manual intervention required."

---

## Output Format

```
=== GB Memory Validation Report ===
WRAM:  [actual] / 8,192 bytes  ([pct]%)  [STATUS]
VRAM:  [actual] / 384 tiles    ([pct]%)  [STATUS]
OAM:   [actual] / 40 sprites   ([pct]%)  [STATUS]

[PASS / WARN / FAIL — overall result]
[If any FAIL: specific guidance per budget above]
```

*ROM bank budgets are reported by the `bank-post-build` skill — run that before this agent.*

---

## Memory Log

**After each run:** Append a snapshot line to:
`~/.claude/projects/-home-mathdaman-code-gmb-nuke-raider/memory/gb-memory-validator.md`

```
[YYYY-MM-DD] WRAM: Z% VRAM: W% OAM: V%  [PASS/WARN/FAIL]
```

Do not duplicate identical consecutive snapshots.
```

**Step 2: Commit**

```bash
git add .claude/agents/gb-memory-validator.md
git commit -m "refactor: gb-memory-validator — remove ROM bank checks (moved to bank-post-build skill)"
```

---

### Task 7: Refactor `gbdk-expert` agent — remove banking guidance

**Files:**
- Modify: `.claude/agents/gbdk-expert.md`

The agent currently has MBC bank switching in its description and domain knowledge. Remove all banking guidance — that's now in `bank-pre-write` + `bank-post-build`.

**Step 1: Edit the agent**

In `.claude/agents/gbdk-expert.md`:

1. Update the `description` frontmatter — remove "MBC bank switching" from the trigger list:

Change:
```
description: Use this agent for GBDK-2020 API questions, Game Boy hardware register usage, sprite/tile/palette setup, CGB color palettes, VBlank timing, interrupt handling, MBC bank switching, and GBDK compilation errors.
```
To:
```
description: Use this agent for GBDK-2020 API questions, Game Boy hardware register usage, sprite/tile/palette setup, CGB color palettes, VBlank timing, interrupt handling, and GBDK compilation errors. Banking questions go to bank-pre-write or bank-post-build skills.
```

2. In the project context block, remove or replace the line:
```
- **Hardware target:** CGB compatible (`-Wm-yc`), MBC1 (`-Wm-yt1`)
```
Keep the line but without implying banking expertise.

3. In `Common Bugs`, remove:
```
- MBC1 bank 0 is always mapped; bank switching only affects 0x4000–0x7FFF
```
Replace with:
```
- MBC bank switching questions → use bank-pre-write / bank-post-build skills
```

**Step 2: Commit**

```bash
git add .claude/agents/gbdk-expert.md
git commit -m "refactor: gbdk-expert — remove banking guidance (moved to bank-pre-write/bank-post-build)"
```

---

### Task 8: Delete `rom-banking` skill

**Files:**
- Delete: `.claude/skills/rom-banking/SKILL.md`
- Delete: `.claude/skills/rom-banking/` (directory)

**Step 1: Delete the skill**

```bash
rm -rf .claude/skills/rom-banking
```

**Step 2: Verify it's gone**

```bash
ls .claude/skills/
```

Expected: `rom-banking` no longer listed.

**Step 3: Commit**

```bash
git add -A .claude/skills/rom-banking
git commit -m "chore: delete rom-banking skill — absorbed into bank-pre-write and bank-post-build"
```

---

### Task 9: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

**Changes needed:**

1. **Remove** the entire `## ROM Banking — Autobanking Conventions` section (replaced by manifest + skills).

2. **Update** the GB skill gates block to reflect new gate flow:

Find:
```
**GB skill gates (mandatory):**
- Before writing any `src/*.c` or `src/*.h` file → invoke `gbdk-expert`
- When debugging any runtime issue → invoke `emulicious-debug`
```

Replace with:
```
**GB skill gates (mandatory):**
- Before writing any `src/*.c` or `src/*.h` file → invoke `bank-pre-write` skill, then `gbdk-expert`
- After a successful build, before smoketest → invoke `bank-post-build` skill, then `gb-memory-validator` agent
- When debugging any runtime issue → invoke `emulicious-debug`
```

3. **Update** the Skills section — add `bank-pre-write` and `bank-post-build`, remove `rom-banking`:

In `### Skills (in `.claude/skills/`)`:

Remove the `rom-banking` entry.

Add:
```
- **`bank-pre-write`** — Hard gate before writing any `src/*.c`/`.h`. Validates manifest entry, pragma, SET_BANK safety. **Invoke before every write.**
- **`bank-post-build`** — Hard gate after successful build. Validates .map symbol placements vs manifest, ROM bank budgets. **Invoke before every smoketest.**
```

4. **Add** manifest maintenance rule after the ROM Banking section is removed. In the `## Scalability Conventions` or near the build section, add:

```
**Bank manifest maintenance:**
Every new `src/*.c` file must have an entry in `bank-manifest.json` before it is written. The `bank-pre-write` skill and `bank_check.py` both enforce this. Every banking-related PR must update ALL artifacts: `bank-manifest.json`, both bank skills, `bank_check.py`, `gbdk-expert`, `gb-memory-validator`, and this file.
```

**Step 1: Make all four edits to CLAUDE.md**

**Step 2: Verify no leftover references to `rom-banking` skill**

```bash
grep -r "rom-banking" CLAUDE.md .claude/
```

Expected: no results (or only in git history).

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md — new gate flow, manifest rule, remove rom-banking skill reference"
```

---

### Task 10: Update memories

**Files:**
- Modify: `~/.claude/projects/-home-mathdaman-code-gmb-nuke-raider/memory/feedback_rom_banking.md`

**Step 1: Update the feedback memory**

Read the current file, then replace its content to reflect the new architecture. The old memory says "fix by moving generated data files to `#pragma bank 2`". The new architecture encodes the fix in the skills.

New content:

```markdown
---
name: feedback_rom_banking
description: ROM banking safety rules — bank manifest is now the source of truth; blank screen at 2 FPS means bank overflow
type: feedback
---

Blank screen at ~1-2 FPS = state code overflowed bank 1. Fix: bump `-Wm-ya` to the next power of 2 in the Makefile.

**Why:** This occurred 3+ times. The root cause is always state_*.c or state_manager.c spilling out of bank 1 because bank 1 got too full.

**How to apply:** The `bank-post-build` skill checks for this automatically after every build. If it fires, bump `-Wm-ya`. Never hardcode `#pragma bank N` on autobanked files — use `bank-manifest.json` and `#pragma bank 255`.

**Architecture as of 2026-03-16:** Banking is enforced by:
1. `bank-manifest.json` — single source of truth for every `src/*.c` bank assignment
2. `bank-pre-write` skill — hard gate before writing any .c/.h file
3. `bank-post-build` skill — hard gate after build, before smoketest
4. `tools/bank_check.py` — Makefile dependency, catches mistakes outside Claude
```

**Step 2: Update MEMORY.md index**

Read `~/.claude/projects/-home-mathdaman-code-gmb-nuke-raider/memory/MEMORY.md`, update the description for `feedback_rom_banking.md`:

Change:
```
- [feedback_rom_banking.md](feedback_rom_banking.md) — Blank screen ~1-2 FPS = state code overflowed bank 1; fix by moving generated data files to `#pragma bank 2`
```

To:
```
- [feedback_rom_banking.md](feedback_rom_banking.md) — Blank screen ~1-2 FPS = bank 1 overflow; fix is bump -Wm-ya. Banking now enforced by bank-manifest.json + bank-pre-write/bank-post-build skills + bank_check.py
```

**Step 3: Commit**

```bash
git add -A  # memories are outside repo, nothing to add — just note the update
# No commit needed for memory files (they live outside the repo)
```

---

### Task 11: Final verification

**Step 1: Run all tests**

```bash
python3 -m unittest tests.test_bank_check -v
make test-tools
make test
```

Expected: all pass.

**Step 2: Full build with bank_check**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: bank_check passes, ROM builds successfully.

**Step 3: Verify AC10 — adding a .c file without manifest entry is blocked**

```bash
# Create a file without a manifest entry
echo '#pragma bank 255' > src/test_new_module.c
GBDK_HOME=/home/mathdaman/gbdk make 2>&1 | grep "ERROR"
# Expected: ERROR: src/test_new_module.c is not in bank-manifest.json
rm src/test_new_module.c
```

**Step 4: Verify rom-banking skill is gone**

```bash
ls .claude/skills/ | grep rom
# Expected: no output
```

**Step 5: Commit final verification evidence**

```bash
git add .claude/settings.local.json  # if any permissions were approved
git commit -m "chore: final verification — all AC criteria met for issue #111"
```

---

### Task 12: Push branch and create PR

**Step 1: Fetch and merge latest master**

```bash
git fetch origin && git merge origin/master
```

**Step 2: Build after merge**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

**Step 3: Run bank-post-build** (invoke `bank-post-build` skill)

**Step 4: Run gb-memory-validator** (invoke the agent)

**Step 5: Smoketest in emulator**

```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb &
```

Wait for user confirmation that the ROM looks correct.

**Step 6: Push and create PR**

```bash
git push -u origin worktree-feat/issue-111-bank-manifest
gh pr create \
  --title "feat: proactive ROM banking safety — manifest, gate skills, artifact consolidation" \
  --body "$(cat <<'EOF'
## Summary
- Adds `bank-manifest.json` as single source of truth for all `src/*.c` bank assignments
- Adds `tools/bank_check.py` (Makefile dependency) that fails the build if any pragma mismatches the manifest
- Adds `bank-pre-write` and `bank-post-build` skills (~300/400 tokens each, replacing ~3000 tokens of scattered banking docs)
- Removes `rom-banking` skill; strips banking sections from `gbdk-expert` and `gb-memory-validator`
- Updates `CLAUDE.md` gate flow; updates memories

## Test plan
- [ ] `python3 -m unittest tests.test_bank_check -v` — all 8 tests pass
- [ ] `make test-tools` — passes
- [ ] `GBDK_HOME=/home/mathdaman/gbdk make` — bank_check passes, ROM builds
- [ ] Adding a `.c` file without manifest entry → `make` exits non-zero with clear error
- [ ] ROM smoketest passes in Emulicious

Closes #111
EOF
)"
```
