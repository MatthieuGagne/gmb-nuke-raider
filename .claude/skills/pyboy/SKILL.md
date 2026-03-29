---
name: pyboy
description: Raw PyBoy 2.7.0 API reference — invoke before writing or extending any PyBoy integration script. Covers emulator control, memory, input, screen, hooks, state, and game wrappers.
---

# PyBoy 2.7.0 API Reference

**Version:** 2.7.0 (currently installed)
**Docs:** https://docs.pyboy.dk/index.html — re-check this URL when upgrading PyBoy.

> This skill documents the **raw PyBoy API**. For the project-specific `GameSession` wrapper, see `.claude/skills/headless-debug/SKILL.md`.

---

## 1. Emulator Control

### Constructor

```python
from pyboy import PyBoy

pyboy = PyBoy(
    gamerom,           # str | file-like — required; ROM filepath or file object
    window="null",     # "null" for headless, "SDL2" for display, "OpenGL", "GLFW"
    scale=3,           # window magnification (ignored when window="null")
    cgb=None,          # None=auto-detect, True=force CGB, False=force DMG
    bootrom=None,      # path to boot ROM (optional)
    sound_volume=0,    # 0-100; set 0 for headless/CI
    log_level="WARNING",
    # less common:
    ram_file=None, rtc_file=None, symbols=None,
    gameshark=None, no_input=False,
)
```

**Headless pattern (use this in all scripts):**

```python
pyboy = PyBoy("build/nuke-raider.gb", window="null")
```

### Context manager (preferred)

```python
with PyBoy("build/nuke-raider.gb", window="null") as pyboy:
    pyboy.tick(60)
# auto-calls pyboy.stop() on exit
```

### tick()

```python
pyboy.tick(count=1, render=True, sound=True) -> bool
```

Advances emulation by `count` frames. Returns `False` when emulation ends (window close / `QUIT` event). Set `render=False` for faster headless runs.

```python
pyboy.tick(300)           # advance 300 frames
pyboy.tick(1, render=False)  # single frame, no render (faster)
```

### stop()

```python
pyboy.stop(save=True, ram_file=None, rtc_file=None)
```

Cleanly shuts down emulator. `save=True` persists battery RAM to the default save file.

### set_emulation_speed()

```python
pyboy.set_emulation_speed(target_speed)
```

- `0` — unlimited (fastest possible, use in CI/scripts)
- `1` — real-time (60 fps)
- `2` — 2× real-time, etc.

---

## 2. Memory Access

### pyboy.memory (PyBoyMemoryView)

Read/write the full Game Boy address space by index or slice:

```python
# Read single byte
val = pyboy.memory[0xC000]          # WRAM byte at 0xC000

# Read slice (returns bytearray)
block = pyboy.memory[0xC000:0xC010] # 16 bytes of WRAM

# Write single byte
pyboy.memory[0xC000] = 42

# Read/write with explicit bank (ROM/SRAM banks)
pyboy.memory[1, 0x4000]             # read ROM bank 1, addr 0x4000
pyboy.memory[1, 0x4000] = 0xFF      # write to bank 1
```

**Memory map summary (GB/GBC):**

| Range | Description |
|-------|-------------|
| `0x0000–0x3FFF` | ROM bank 0 |
| `0x4000–0x7FFF` | ROM bank N (switchable) |
| `0x8000–0x9FFF` | VRAM |
| `0xA000–0xBFFF` | External RAM (SRAM) |
| `0xC000–0xCFFF` | WRAM bank 0 |
| `0xD000–0xDFFF` | WRAM bank 1 (GBC switchable) |
| `0xFE00–0xFE9F` | OAM |
| `0xFF00–0xFF7F` | I/O registers |
| `0xFF80–0xFFFE` | HRAM |

### Project WRAM debug addresses (matches src/config.h)

| Address | Size | Purpose |
|---------|------|---------|
| `0xDF80` | 64 bytes | `DBG_STR` ring buffer content |
| `0xDFC0` | 1 byte | ring buffer write index |
| `0xDFC1` | 1 byte | `music_tick()` call counter (wraps at 256) |

### register_file (CPU registers — hook callbacks only)

```python
# Available inside hook callbacks:
r = pyboy.register_file
r.A   # accumulator
r.B, r.C, r.D, r.E, r.H, r.L   # 8-bit general registers
r.BC, r.DE, r.HL                # 16-bit pairs
r.SP  # stack pointer
r.PC  # program counter
```

---

## 3. Input

### button() — high-level (preferred)

```python
pyboy.button(input, delay=1)
```

Sends a momentary press + auto-release after `delay` frames. `input` is a string:

| String | Game Boy button |
|--------|----------------|
| `"a"` | A |
| `"b"` | B |
| `"start"` | Start |
| `"select"` | Select |
| `"left"` | D-pad Left |
| `"right"` | D-pad Right |
| `"up"` | D-pad Up |
| `"down"` | D-pad Down |

```python
pyboy.button("start")          # press+release Start next frame
pyboy.button("a", delay=3)     # hold A for 3 frames then release
```

### button_press() / button_release() — sustained hold

```python
pyboy.button_press("right")    # hold Right indefinitely
pyboy.tick(30)
pyboy.button_release("right")  # release
```

### send_input() — low-level WindowEvent

```python
from pyboy.utils import WindowEvent

pyboy.send_input(WindowEvent.PRESS_BUTTON_A)
pyboy.tick(1)
pyboy.send_input(WindowEvent.RELEASE_BUTTON_A)
```

**Full WindowEvent constants:**

```
# Button press/release
WindowEvent.PRESS_BUTTON_A       WindowEvent.RELEASE_BUTTON_A
WindowEvent.PRESS_BUTTON_B       WindowEvent.RELEASE_BUTTON_B
WindowEvent.PRESS_BUTTON_START   WindowEvent.RELEASE_BUTTON_START
WindowEvent.PRESS_BUTTON_SELECT  WindowEvent.RELEASE_BUTTON_SELECT

# D-pad press/release
WindowEvent.PRESS_ARROW_LEFT     WindowEvent.RELEASE_ARROW_LEFT
WindowEvent.PRESS_ARROW_RIGHT    WindowEvent.RELEASE_ARROW_RIGHT
WindowEvent.PRESS_ARROW_UP       WindowEvent.RELEASE_ARROW_UP
WindowEvent.PRESS_ARROW_DOWN     WindowEvent.RELEASE_ARROW_DOWN

# Emulator control
WindowEvent.QUIT
WindowEvent.PAUSE_TOGGLE
WindowEvent.PAUSE
WindowEvent.UNPAUSE
WindowEvent.STATE_SAVE
WindowEvent.STATE_LOAD
WindowEvent.RELEASE_SPEED_UP
WindowEvent.CYCLE_PALETTE
WindowEvent.PASS
```

---

## 4. Screen & Rendering

### pyboy.screen

```python
screen = pyboy.screen

# PIL Image (144×160 RGB)
img = screen.image
img.save("screenshot.png")

# NumPy array (144×160×4 RGBA uint8) — requires numpy
arr = screen.ndarray

# Scroll position per scanline
positions = screen.tilemap_position_list  # list of (x, y) per scanline
```

**Screenshot pattern:**

```python
pyboy.tick(1, render=True)      # must render=True to get a fresh frame
pyboy.screen.image.save("debug.png")
```

### pyboy.sound

```python
audio = pyboy.sound
samples = audio.ndarray   # shape (801, 2) stereo PCM int16
```

---

## 5. Hooks & Breakpoints

Install a callback at a specific ROM bank + address (fires every time the CPU executes that address):

```python
def my_hook(pyboy, mb, context):
    # mb = MotherBoard (internal); use pyboy.register_file for CPU state
    val = pyboy.memory[0xDFC1]
    print(f"hook fired, tick={val}")

pyboy.hook_register(bank=0, addr=0x1234, callback=my_hook, context=None)

# With .sym file symbols (requires symbols= in constructor):
pyboy.hook_register(None, "Main.music_tick", my_hook, None)

# Deregister
pyboy.hook_deregister(bank=0, addr=0x1234)
```

---

## 6. State Save / Load

```python
import io

# Save snapshot
buf = io.BytesIO()
pyboy.save_state(buf)
buf.seek(0)

# Restore snapshot
pyboy.load_state(buf)
```

Useful for branching test scenarios without re-booting the ROM each time.

---

## 7. Game Wrappers

```python
gw = pyboy.game_wrapper       # auto-detected wrapper (generic or game-specific)
gw.start_game()               # enter gameplay from title screen
gw.reset_game()               # reset to initial game state
shape = gw.shape              # (width, height) in tiles
```

### game_area() — ML-optimized tilemap

```python
tiles = pyboy.game_area()     # 2D memoryview of on-screen tile IDs

# Restrict to a subregion:
pyboy.game_area_dimensions(x=0, y=0, width=20, height=18, follow_scrolling=True)

# Custom tile ID mapping (384 entries for DMG, 768 for CGB):
pyboy.game_area_mapping(my_mapping, sprite_offset=0)
```

### tilemap_background / tilemap_window

```python
tile_id = pyboy.tilemap_background[col, row]          # single tile
row_ids = pyboy.tilemap_background[0:20, 9]           # row slice
region  = pyboy.tilemap_background[0:10, 0:9]         # 2D slice
```

---

## 8. Cartridge Utilities

```python
pyboy.cartridge_title          # str — ROM title (max 11 chars)
tile  = pyboy.get_tile(id)     # Tile object by identifier
spr   = pyboy.get_sprite(idx)  # Sprite object by OAM index (0-39)
sprs  = pyboy.get_sprite_by_tile_identifier([id1, id2], on_screen=True)
```

---

## Quick-start headless script template

```python
from pyboy import PyBoy

with PyBoy("build/nuke-raider.gb", window="null") as pyboy:
    pyboy.set_emulation_speed(0)   # unlimited speed

    # Boot to title screen
    pyboy.tick(300)

    # Press Start to enter game
    pyboy.button("start")
    pyboy.tick(60)

    # Read a WRAM value
    val = pyboy.memory[0xDFC1]
    print(f"music_tick counter: {val}")

    # Capture screenshot
    pyboy.tick(1, render=True)
    pyboy.screen.image.save("debug.png")
```
