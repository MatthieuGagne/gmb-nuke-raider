---
name: gbdk-expert
description: Use when writing or reviewing GBDK-2020 code — API calls, hardware registers, sprite/tile/palette setup, VBlank timing, CGB color palettes, interrupt handling, MBC banking, or GBDK compilation errors. Use during planning to verify API names and constraints before writing tests.
---

# GBDK Expert — Wasteland Racer

## Memory
At the start of any GBDK-related task, read:
`~/.claude/projects/-home-mathdaman-code-gmb-wasteland-racer/memory/gbdk-expert.md`

After completing the task, append any new bugs, API gotchas, or confirmed patterns to that file. Do not duplicate existing entries.

## Reference Documentation
**Pan Docs** (authoritative Game Boy hardware reference): https://gbdev.io/pandocs/

Use `WebFetch` to look up Pan Docs pages when you need precise hardware register details, timing values, memory map addresses, or behavior not covered in this skill. Key sections:
- Memory map: https://gbdev.io/pandocs/Memory_Map.html
- LCD / VRAM timing: https://gbdev.io/pandocs/STAT.html
- OAM / sprites: https://gbdev.io/pandocs/OAM.html
- CGB registers: https://gbdev.io/pandocs/CGB_Registers.html
- Interrupts: https://gbdev.io/pandocs/Interrupts.html
- MBC1 banking: https://gbdev.io/pandocs/MBC1.html

When Pan Docs contradicts your cached knowledge, trust Pan Docs and update memory.

## Hardware Constraints
- Screen: 160×144 pixels
- WRAM: 8KB | VRAM: 8KB (CGB: 2 banks via `VBK_REG`)
- OAM: 40 sprites max, 10 per horizontal scanline
- Tiles: 8×8 pixels, 4 colors per palette
- CGB palettes: 8 BG + 8 OBJ, 4 colors each
- ROM: MBC1, 16KB banks (bank 0 always mapped; bank switching only affects 0x4000–0x7FFF)

## Key Headers
- `gb/gb.h` — core (joypad, sprites, tiles, DISPLAY_ON/OFF, wait_vbl_done)
- `gb/cgb.h` — CGB: `set_bkg_palette()`, `set_sprite_palette()`, `VBK_REG`
- `gb/hardware.h` — raw hardware registers
- `gbdk/console.h` — text output
- `stdio.h` — **required for `printf`** (NOT in console.h — omitting causes implicit declaration errors)

## Critical Rules

### VRAM Writes
Always guard VRAM writes with `wait_vbl_done()` **unless display is off** (`DISPLAY_OFF`).
Writing to VRAM outside VBlank causes graphical corruption.

### Sprite Init Sequence
```c
SPRITES_8x8;                                  /* safe anytime — LCDC flag */
wait_vbl_done();                              /* required if display is ON */
set_sprite_data(0, 1, player_tile_data);      /* correct API name */
set_sprite_tile(0, 0);
move_sprite(0, start_x, start_y);
SHOW_SPRITES;
```

**`set_sprite_data` — not `set_sprite_tile_data`** (that name does not exist).
Aliases: `set_sprite_2bpp_data` → `set_sprite_data`, `set_sprite_1bpp_data` for 1bpp source.

### Sprite Coordinate System
`move_sprite(nb, x, y)` writes raw OAM. Screen pixel = (x − 8, y − 16).
- `DEVICE_SPRITE_PX_OFFSET_X = 8`, `DEVICE_SPRITE_PX_OFFSET_Y = 16`
- **Fully visible bounds (8×8): x ∈ [8, 167], y ∈ [16, 159]**
- Hidden when x ≥ 168 or y ≥ 160
- **Common mistake:** using 152/136 as max — these cut off ~15px of reachable screen area

### CGB Palettes
- Format: 5-bit RGB packed with `RGB(r, g, b)` macro (values 0–31)
- Sprite color index 0 is **always transparent** — usable indices: 1, 2, 3
- All BG tiles default to palette 0 unless you write the attribute map (VRAM bank 1)
- `set_bkg_palette(0, 1, pal)` controls console text color

### 2bpp Tile Format
Each row = 2 bytes: byte0 = low bit plane, byte1 = high bit plane.
`color_index = (high_bit << 1) | low_bit` per pixel column.
- `0xFF, 0xFF` → all pixels index 3 | `0x00, 0x00` → all pixels index 0 (transparent)

## Console / Font
- `printf` uses BG tile map (SCRN0) as 20×18 char grid; mapping: `ascii − 0x20 = tile index`
- Default font works without explicit init; use `font_init()` / `font_load()` for multi-font API
- `font_ibm` uses tiles 0–95 — load game BG tiles starting at ID 96+ to avoid overwriting
- `M_NO_SCROLL` wraps cursor instead of scrolling; `M_NO_INTERP` disables special chars

## SDCC Gotchas
- **No compound literals**: `(const uint16_t[]){...}` → use named `static const` arrays
- **Warning "conditional flow changed by optimizer: so said EVELYN"** — harmless, not an error
- Prefer `uint8_t` loop counters; avoid `float`/`double`; no `malloc`/`free`

## Verification
After changes: run `/test` (host-side, gcc) then `/build` (full ROM).
