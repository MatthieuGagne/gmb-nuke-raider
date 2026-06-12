---
name: screenshot
description: Use when capturing a headless screenshot to diagnose a visual bug or inspect game/WRAM state without launching Emulicious — invoke before running tools/screenshot.py to get the current API (navigation step format, button names, address syntax, viewing the result in conversation).
---

# screenshot — Headless Game Boy Screenshot Capture

## When to Use

Invoke this skill before running `tools/screenshot.py` so you have the correct API.
Use when the user reports a visual bug or unexpected behavior and you need to *see* the
game state yourself to diagnose it.

## Game Manifest

Before writing any navigation steps, read `build/game-manifest.json`. It contains:

- `navigation.overmap_to_track` — BFS tile-direction paths from hub_spawn to each track entry; multiply `len(path) * travel_frames_per_tile` for frame delays
- `navigation.overmap_to_hub` — paths to city hubs
- `controls` — button mappings per state; `prerace.cursor_to_start` gives the exact DOWN-press count to reach the START row
- `tracks` — per-track spawn pixel coords, racer waypoints, checkpoint rects
- `symbols` — WRAM addresses for key debugging state (`_cam_scx_shadow`, `_px`, `_py`, `_hp`, `_active_lap_count`, `_cp_next`, `_racer_active`, etc.)

Prefer manifest values over hardcoded coordinates or guessed paths.

## Setup

If PyBoy is not installed:
```bash
pip install -r requirements.txt
```

## Command

```bash
py tools/screenshot.py \
  [--rom  build/nuke-raider.gb]           # default: auto-resolved from script location (worktree-safe)
  [--map  build/nuke-raider.map]           # default: auto-resolved; used for symbol lookup
  [--out  build/screenshot.png]            # default: build/screenshot.png (worktree-safe)
  [--steps     '[...]']                    # inline JSON steps
  [--steps-file path/to/steps.json]        # steps from file (avoids shell-quoting issues)
```

## Navigation Steps (JSON array)

### advance — tick N frames (fast-forward)
```json
{"action": "advance", "frames": 120}
```

### press — press one or more buttons
```json
{"action": "press", "buttons": ["start"], "delay": 1}
```
- `buttons`: list of button names (see below)
- `delay`: frames to hold before release (default 1)
- Buttons pressed simultaneously if multiple listed

### wait_memory — advance until memory address equals value
```json
{"action": "wait_memory", "address": "_game_state", "value": 3, "max_frames": 600}
```
- `address`: hex string (`"0xC0B1"`) or SDCC symbol name (`"_game_state"`)
- `value`: integer to wait for
- `max_frames`: timeout — on timeout, saves screenshot to `--out` path and exits non-zero
- Symbols resolved from `build/nuke-raider.map`

### screenshot — save mid-sequence screenshot
```json
{"action": "screenshot", "out": "build/before-press.png"}
```
If `out` is omitted, uses `--out` default (`build/screenshot.png`).

## Button Names

`"a"` `"b"` `"start"` `"select"` `"up"` `"down"` `"left"` `"right"`

Case-insensitive (normalized to lowercase internally).

## Address Resolution

- Hex string: `"0xC0B1"` — used directly
- Symbol name: `"_cam_y"` — looked up in `build/nuke-raider.map`

Find any symbol:
```bash
grep "_symbol_name" build/nuke-raider.map
```

## Using Steps File (complex sequences)

Write steps to a JSON file to avoid shell-quoting issues:
```bash
cat > /tmp/steps.json << 'EOF'
[
  {"action": "advance", "frames": 120},
  {"action": "press", "buttons": ["start"]},
  {"action": "advance", "frames": 60},
  {"action": "screenshot", "out": "build/mid-overmap.png"},
  {"action": "press", "buttons": ["left"]},
  {"action": "advance", "frames": 60}
]
EOF
py tools/screenshot.py --steps-file /tmp/steps.json
```

## IMPORTANT: Viewing the Screenshot

After running the script, **always use the `Read` tool** on the output path to view the image
in the conversation:

```
Read("build/screenshot.png")
```

Claude is multimodal — the `Read` tool displays PNG files inline. Without this step, you
cannot see the result.

## Error Handling

- **ROM not found**: build first with `make clean && make`
- **wait_memory timeout**: screenshot of current state is saved; check the state machine values with `grep "_state" build/nuke-raider.map`
- **PyBoy crash mid-navigation**: best-effort screenshot saved; exit non-zero
- **Symbol not found**: run `grep "_your_symbol" build/nuke-raider.map` to find the exact name SDCC emitted

## Headless WRAM Read (State Inspection)

Use when the symptom is a wrong WRAM value, not a visual glitch — faster than launching Emulicious.

### Pattern

**1. Export debug globals in `src/foo.c` alongside the static variables:**
```c
uint8_t dbg_foo_armed;
int8_t  dbg_foo_pvy;
uint8_t dbg_foo_cps;
```

**2. Find their addresses after building:**
```bash
grep "dbg_foo" build/nuke-raider.map
```
Addresses shift if WRAM layout changes — always re-grep after a new build.

**3. Read them via PyBoy:**
```python
from pyboy import PyBoy
pyboy = PyBoy('build/nuke-raider.gb', window='null')   # no cgb_mode kwarg — causes KeyError
pyboy.set_emulation_speed(0)
# ... navigate with pyboy.send_input() + pyboy.advance_frame() ...
val = pyboy.memory[0xC373]   # address from .map grep
```

**CRITICAL:** `window='null'` is the correct headless flag. Do NOT pass `cgb_mode=True` — it raises `KeyError: Unknown keyword argument`.

### Combined workflow

1. Use `screenshot.py` with `wait_memory` steps to navigate to the exact game state
2. Then read multiple adjacent WRAM bytes directly from `pyboy.memory[addr]`
3. Compare values against expected to confirm/rule out hypotheses without opening Emulicious
