---
name: headless-debug
description: Autonomous 5-step debug loop using PyBoy headless emulator — boot ROM, simulate inputs, read WRAM debug log, hypothesize, fix, verify
---

# Headless Debug Skill

Use this skill when you need to autonomously reproduce a runtime bug, observe state, and verify a fix — without a human launching Emulicious.

## When to use

- Reproducing timing bugs (VBlank, music_tick double-ticks)
- Checking WRAM values after N frames in a known game state
- Verifying a fix doesn't regress in CI-style

## Prerequisites

- PyBoy installed: `pip3 install pyboy`
- Debug ROM built: `make build-debug` (compiles with `-DDEBUG`)
- `tests/integration/helpers.py` exists (see GameSession API)

## The 5-Step Loop

### Step 1 — Reproduce

Write an ad-hoc script in `tests/integration/`:

```python
from tests.integration.helpers import GameSession

with GameSession.boot("build/nuke-raider.gb") as s:
    s.advance(300)   # title screen, no input
    tick = s.read_wram(0xDFC1)
    print("tick counter after 300 frames:", tick)
```

Run: `make build-debug && python3 tests/integration/my_script.py`

### Step 2 — Observe

After reaching the buggy state:
- `s.read_wram(addr)` — read one WRAM byte at a known address
- `s.read_debug_log()` — drain the WRAM ring buffer (returns list of strings logged by `DBG_STR`)
- `s.screenshot("out.png")` — capture screen; use the Read tool to view it

### Step 3 — Hypothesize

From log + WRAM values + screenshots, form a theory. Update the hypothesis queue in the bug issue.

### Step 4 — Fix

Edit `src/*.c`, run `make build-debug`, re-run the exact same script. Compare observations.

### Step 5 — Promote

If the ad-hoc script is generally useful (reproducible scenario), extract it into `tests/integration/` with a clear docstring.

## WRAM debug addresses (must match src/config.h)

| Address | Size | Purpose |
|---------|------|---------|
| `0xDF80` | 64 bytes | `DBG_STR` ring buffer content |
| `0xDFC0` | 1 byte | ring buffer write index |
| `0xDFC1` | 1 byte | `music_tick()` call counter (wraps at 256) |

## GameSession API

```python
GameSession.boot(rom_path, headless=True)  # returns session
session.advance(frames)                    # tick N frames
session.press(["A", "START"], hold_frames=3)
session.read_wram(addr)                    # int 0-255
session.read_debug_log()                   # list[str]
session.screenshot("path.png")
session.close()
```
