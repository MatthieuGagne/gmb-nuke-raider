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

**Before writing or extending any PyBoy script**, invoke the `pyboy` skill for the full raw API reference (constructor flags, memory access, input, screen, hooks, state management):

```
Skill tool → skill: "pyboy"
```

The `GameSession` wrapper below abstracts the most common operations. When you need something the wrapper doesn't expose (hooks, save/load state, tilemap, game wrappers), the `pyboy` skill has the raw API.

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

If the ad-hoc script is generally useful (reproducible scenario), promote it into `tests/integration/test_regression.py` as a new test function — do not create a separate file unless the scenario is completely independent of the state traversal. Always ask the user before adding or modifying integration tests.

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
session.write_wram(addr, value)            # write one byte to WRAM
session.read_debug_log()                   # list[str]
session.screenshot("path.png")
session.close()
```

## WRAM Symbol Lookup

`find_wram_sym_from_map(map_path, "_symbol")` — finds **non-static global** WRAM variables in the `.map` file.

`find_wram_read_in_fn(noi_path, rom_path, "_getter_fn")` — finds **static** file-scope WRAM variables by disassembling a getter function from the ROM binary. Use this when SDCC doesn't export the variable name (all `static` vars). Requires `.noi` from `make build-debug`.

```python
from tests.integration.helpers import find_wram_read_in_fn, find_wram_sym_from_map

# static var (e.g. `static uint8_t hp` in damage.c):
hp_addr = find_wram_read_in_fn("build/nuke-raider.noi", "build/nuke-raider.gb", "_damage_get_hp")

# non-static global (e.g. `uint8_t current_state`):
state_addr = find_wram_sym_from_map("build/nuke-raider.map", "_current_state")
```

## Integration Regression Suite

`tests/integration/test_regression.py::test_all_states` navigates every game state in one session. Run it after any fix that touches state transitions:

```bash
make test-integration
```

When promoting an ad-hoc script to a permanent test, add a new function to `test_regression.py` — do not create a new file unless the scenario is independent. Always ask the user before adding or modifying integration tests.
