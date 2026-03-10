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
**Single-page version** (use `WebFetch` on this for any hardware detail you're unsure about): https://gbdev.io/pandocs/single.html

When uncertain about hardware behavior, registers, timing, or any spec detail — fetch the single-page URL with a targeted prompt rather than guessing. It contains the full specification in one document.

Key individual pages:
- Tile data / 2bpp: https://gbdev.io/pandocs/Tile_Data.html
- LCDC register: https://gbdev.io/pandocs/LCDC.html
- STAT / PPU modes: https://gbdev.io/pandocs/STAT.html
- OAM / sprites: https://gbdev.io/pandocs/OAM.html
- Palettes (DMG+CGB): https://gbdev.io/pandocs/Palettes.html
- CGB registers: https://gbdev.io/pandocs/CGB_Registers.html
- Interrupts: https://gbdev.io/pandocs/Interrupts.html
- MBC1 banking: https://gbdev.io/pandocs/MBC1.html
- Joypad: https://gbdev.io/pandocs/Joypad_Input.html
- Timer: https://gbdev.io/pandocs/Timer_and_Divider_Registers.html
- Audio/APU: https://gbdev.io/pandocs/Audio.html
- OAM DMA: https://gbdev.io/pandocs/OAM_DMA_Transfer.html

When Pan Docs contradicts your cached knowledge, trust Pan Docs and update memory.

---

## Memory Map

| Address     | Size     | Description                            |
|-------------|----------|----------------------------------------|
| 0000–3FFF   | 16 KiB   | ROM Bank 00 (fixed)                    |
| 4000–7FFF   | 16 KiB   | ROM Banks 01–NN (switchable via MBC)   |
| 8000–9FFF   | 8 KiB    | VRAM (CGB: bank 0/1 via FF4F/VBK)     |
| A000–BFFF   | 8 KiB    | External RAM (cartridge, if present)   |
| C000–CFFF   | 4 KiB    | WRAM bank 0 (fixed)                    |
| D000–DFFF   | 4 KiB    | WRAM banks 1–7 (CGB switchable FF70)  |
| E000–FDFF   | —        | Echo RAM — mirrors C000–DDFF, avoid   |
| FE00–FE9F   | 160 B    | OAM (40 sprites × 4 bytes)            |
| FEA0–FEFF   | —        | Not usable (Nintendo prohibited)       |
| FF00–FF7F   | 128 B    | I/O registers                          |
| FF80–FFFE   | 127 B    | HRAM (fast, stack-safe)                |
| FFFF        | 1 B      | IE — Interrupt Enable register         |

**Key I/O register addresses:**
- FF00: Joypad (P1/JOYP)
- FF0F: IF — Interrupt Flag
- FF03: DIV | FF05: TIMA | FF06: TMA | FF07: TAC (Timer)
- FF40: LCDC | FF41: STAT | FF42/43: SCY/SCX | FF44: LY | FF45: LYC
- FF46: OAM DMA trigger
- FF47: BGP | FF48: OBP0 | FF49: OBP1 (DMG palettes)
- FF4F: VBK (CGB VRAM bank) | FF4D: KEY1 (CGB speed switch)
- FF51–FF55: HDMA (CGB DMA)
- FF68/FF69: BCPS/BCPD (CGB BG palette) | FF6A/FF6B: OCPS/OCPD (CGB OBJ palette)
- FF70: SVBK (CGB WRAM bank)
- FFFF: IE — Interrupt Enable

---

## Hardware Constraints
- Screen: 160×144 pixels
- WRAM: 8 KB | VRAM: 8 KB (CGB: 2 banks via `VBK_REG` at FF4F)
- OAM: 40 sprites max, 10 per horizontal scanline
- Tiles: 8×8 pixels, 4 colors per palette; each tile = 16 bytes (2bpp)
- CGB palettes: 8 BG + 8 OBJ, 4 colors each (64 bytes each palette RAM)
- ROM: MBC1, 16 KB banks; bank 0 always at 0000–3FFF; bank switching affects 4000–7FFF only

---

## LCDC Register (FF40)

| Bit | Name                        | 0 = …           | 1 = …          |
|-----|-----------------------------|-----------------|----------------|
| 7   | LCD & PPU enable            | Off             | On             |
| 6   | Window tile map area        | $9800           | $9C00          |
| 5   | Window enable               | Off             | On             |
| 4   | BG & Window tile data area  | $8800 (signed)  | $8000 (unsigned)|
| 3   | BG tile map area            | $9800           | $9C00          |
| 2   | OBJ size                    | 8×8             | 8×16           |
| 1   | OBJ enable                  | Off             | On             |
| 0   | BG & Window enable/priority | Off (DMG: blank)| On             |

LCDC can be written at any time (PPU never locks it).

---

## PPU Modes & VRAM Access

| Mode | Name          | VRAM  | OAM   | Duration (approx.)          |
|------|---------------|-------|-------|-----------------------------|
| 0    | HBlank        | Free  | Free  | ~204 dots (variable)        |
| 1    | VBlank        | Free  | Free  | Lines 144–153 (~4560 dots)  |
| 2    | OAM Scan      | Free  | Locked| ~80 dots                    |
| 3    | Pixel Transfer| Locked| Locked| ~172 dots (variable)        |

- 1 dot = 1 T-cycle (DMG / CGB normal speed); 2 T-cycles in CGB double speed
- Safe VRAM write window: Mode 0 (HBlank), Mode 1 (VBlank), or with display off
- **`wait_vbl_done()` waits for VBlank (Mode 1) — always call before VRAM writes when display is on**
- BCPD/OCPD (CGB palette RAM) also locked during Mode 3
- Mode 3 duration varies: **172–289 dots** depending on scroll position, window, and sprite count penalties

**Frame timing:**
- 1 frame = 154 scanlines × 456 dots = 70,224 dots total
- ~59.7 fps (not 60); frame period ≈ 16.74 ms
- VBlank window = lines 144–153 = ~1.09 ms (use it wisely)

**Window rendering gotcha:** The window has an internal line counter that increments only when the window is visible on screen. Disabling the window mid-frame and re-enabling it later does not reset the counter — the window resumes from where it left off within the same frame.

**STAT interrupt quirk (DMG/MGB/SGB):** Writing to STAT during OAM scan, HBlank, VBlank, or LY=LYC can spuriously trigger the LCD STAT interrupt on original DMG hardware. This quirk is absent on GBC running in CGB mode. Avoid writing to STAT while the display is on unless you account for this.

---

## OAM Sprite Attributes

Each sprite = 4 bytes at FE00–FE9F:

| Byte | Field      | Details                                                  |
|------|------------|----------------------------------------------------------|
| 0    | Y position | Screen Y = OAM_Y − 16; hidden if 0 or ≥160              |
| 1    | X position | Screen X = OAM_X − 8; hidden if 0 or ≥168               |
| 2    | Tile index | From $8000 block; 8×16 mode: bit 0 ignored (even=top)   |
| 3    | Flags      | See below                                                |

**Flags byte (byte 3):**
| Bit | Meaning                                                         |
|-----|-----------------------------------------------------------------|
| 7   | BG priority: 0=sprite on top, 1=BG/Win colors 1–3 cover sprite |
| 6   | Y flip                                                          |
| 5   | X flip                                                          |
| 4   | DMG palette: 0=OBP0, 1=OBP1                                    |
| 3   | CGB VRAM bank: 0=bank 0, 1=bank 1                              |
| 2–0 | CGB OBJ palette 0–7                                            |

**Drawing priority (non-CGB):** lower X = higher priority; ties broken by OAM index.
**Drawing priority (CGB):** OAM index only (first entry wins).

**CGB BG-to-OBJ priority** is controlled by three flags simultaneously:
- LCDC bit 0: when 0, objects always appear on top of BG/Win regardless of other flags
- BG map attribute bit 7 (VRAM bank 1): when 1, BG colors 1–3 cover objects
- OAM attribute bit 7: when 1, BG/Win colors 1–3 cover object

**OAM corruption bug (DMG/MGB/SGB/SGB2):** Reading $FEA0–$FEFF while OAM is blocked (Modes 2/3) triggers OAM corruption. Avoid accessing this range. On CGB the behavior varies by revision.

---

## Tile Data Format (2bpp)

- Each 8×8 tile = 16 bytes; each row = 2 bytes
- Byte N = low bit plane, Byte N+1 = high bit plane
- Pixel color index: `(high_bit << 1) | low_bit`, bit 7 = leftmost pixel
- `0xFF, 0xFF` → all pixels color 3 | `0x00, 0x00` → all pixels color 0

**Addressing modes:**
- `$8000` mode (unsigned, tiles 0–255): sprites always use this; BG/Win when LCDC.4=1
- `$8800` mode (signed, tiles -128–127 mapped via $9000): BG/Win when LCDC.4=0

CGB: VRAM bank 1 holds 384 additional tiles (total 768 tiles per bank pair).

---

## Palettes

### DMG
- **BGP (FF47):** 4×2-bit entries, index→shade: 0=white…3=black
- **OBP0/OBP1 (FF48/FF49):** same format; index 0 always transparent for sprites

### CGB
- **BCPS (FF68):** BG palette index register; bit 7 = auto-increment on write
- **BCPD (FF69):** BG palette data (RGB555, little-endian; 8 palettes × 4 colors × 2 bytes = 64 bytes)
- **OCPS (FF6A):** OBJ palette index register (same format as BCPS)
- **OCPD (FF6B):** OBJ palette data
- Color format: `RGB(r, g, b)` macro, values 0–31 (5-bit per channel)
- OBJ color index 0 is **always transparent**
- **Cannot write BCPD/OCPD during PPU Mode 3**

---

## Interrupts

| Interrupt | Bit | Vector | Priority |
|-----------|-----|--------|----------|
| VBlank    | 0   | $0040  | Highest  |
| LCD STAT  | 1   | $0048  |          |
| Timer     | 2   | $0050  |          |
| Serial    | 3   | $0058  |          |
| Joypad    | 4   | $0060  | Lowest   |

- **IE (FFFF):** enable bits | **IF (FF0F):** pending flags
- ISR costs 5 M-cycles (2 wait + 2 push PC + 1 jump)
- `ei` effect is delayed by one instruction
- GBDK: use `add_VBL(handler)` / `add_LCD(handler)` etc. to register ISRs

---

## MBC1 Banking

| Address Range | Register       | Function                                      |
|---------------|----------------|-----------------------------------------------|
| 0000–1FFF     | RAM Enable     | Write $0A to enable ext RAM, $00 to disable   |
| 2000–3FFF     | ROM Bank (low) | 5-bit register; 0 treated as 1 (no bank 0 dup)|
| 4000–5FFF     | Upper bits     | 2-bit: upper ROM bits (large ROM) or RAM bank |
| 6000–7FFF     | Mode           | 0=simple (default), 1=advanced                |

- Simple mode (0): upper 2 bits only affect 4000–7FFF; 0000–3FFF always bank 0
- Advanced mode (1): upper 2 bits also switch 0000–3FFF and RAM
- Max: 2 MiB ROM (7 bits), 32 KiB RAM; writing 0 to ROM bank register → behaves as 1

---

## Joypad (FF00 / P1)

| Bit | Meaning when written       | Bit | Meaning when read (0=pressed) |
|-----|---------------------------|-----|-------------------------------|
| 5   | Select action buttons      | 3   | Start / Down                  |
| 4   | Select D-pad               | 2   | Select / Up                   |
| —   | —                          | 1   | B / Left                      |
| —   | —                          | 0   | A / Right                     |

- Write bit 5=0 to read action buttons; bit 4=0 to read D-pad; both=1 → reads $F
- Bits are **active-low**: 0 = pressed, 1 = released
- Read multiple times and use the last value for debounce stability

---

## Timer Registers

| Register | Address | Purpose                                                        |
|----------|---------|----------------------------------------------------------------|
| DIV      | FF03    | Divider — always increments; **any write resets it to 0**     |
| TIMA     | FF05    | Timer counter — increments at TAC frequency; triggers interrupt on overflow |
| TMA      | FF06    | Timer modulo — reloaded into TIMA on overflow                 |
| TAC      | FF07    | Timer control: bit2=enable, bits1–0=clock select              |

**TAC clock select:**
| Bits 1–0 | TIMA frequency |
|----------|----------------|
| 00       | 4096 Hz (~1024 cycles/tick) |
| 01       | 262144 Hz (~16 cycles/tick) |
| 10       | 65536 Hz (~64 cycles/tick)  |
| 11       | 16384 Hz (~256 cycles/tick) |

- GBDK: use `TMA_REG`, `TIMA_REG`, `TAC_REG` from `gb/hardware.h`
- Timer interrupt = bit 2 of IE/IF; handler registered via `add_TIM(handler)`

---

## OAM DMA Transfer

- Triggered by writing source address high byte to FF46 (e.g., `0xC0` copies from $C000)
- Transfers 160 bytes (40 sprites × 4 bytes) from source to OAM ($FE00–$FE9F)
- Takes **160 M-cycles** (640 dots normal speed; 320 dots CGB double speed)
- **During DMA, CPU can only access HRAM ($FF80–$FFFE)** — the DMA routine must run from HRAM
- CGB allows WRAM access during cartridge (MBC) DMA, but not during OAM DMA
- Avoid triggering interrupts during DMA (stack accesses to WRAM corrupt transfer)
- GBDK handles OAM DMA internally via `shadow_OAM` and `hOAMCopy` — don't trigger FF46 manually unless you know what you're doing

---

## Audio / APU

Four channels — all run off the master clock, fully synced with CPU/PPU:
- **CH1** — Pulse with frequency sweep
- **CH2** — Pulse (no sweep)
- **CH3** — Wave (arbitrary 32-sample 4-bit waveform from FF30–FF3F)
- **CH4** — Noise (LFSR)

Key registers:
- FF24: Master volume (NR50) — left/right channel volume
- FF25: Channel panning (NR51) — which channels play left/right
- FF26: Audio master control (NR52) — bit7=sound on/off; bits3–0=channel active (RO)

Length timers tick at 256 Hz; envelopes (CH1/CH2/CH4) tick at 64 Hz.
CH3 length counter cuts off at 256 steps; CH1/CH2/CH4 cut off at 64 steps.

**Note:** GBDK provides a music driver; raw APU register access is needed only for sound effects or custom engines. Fetch https://gbdev.io/pandocs/single.html for full APU register details.

---

## CGB Extra Registers

| Register | Address | Purpose                                         |
|----------|---------|-------------------------------------------------|
| KEY1     | FF4D    | Speed switch: bit0=armed, bit7(RO)=current speed|
| VBK      | FF4F    | VRAM bank: bit 0 only (0=bank0, 1=bank1)        |
| HDMA1–4  | FF51–54 | DMA source/dest (source high/low, dest high/low)|
| HDMA5    | FF55    | DMA length+mode (bit7: 0=GDMA, 1=HBlank DMA)   |
| SVBK     | FF70    | WRAM bank (1–7 → D000–DFFF; 0 treated as 1)     |

---

## Key Headers
- `gb/gb.h` — core (joypad, sprites, tiles, DISPLAY_ON/OFF, wait_vbl_done)
- `gb/cgb.h` — CGB: `set_bkg_palette()`, `set_sprite_palette()`, `VBK_REG`
- `gb/hardware.h` — raw hardware registers
- `gbdk/console.h` — text output
- `stdio.h` — **required for `printf`** (NOT in console.h — omitting causes implicit declaration errors)

---

## Critical Rules

### LCD Disable Warning
**Only disable the LCD during VBlank.** Turning off LCDC bit 7 outside VBlank can physically damage real hardware. In GBDK:
```c
wait_vbl_done();
DISPLAY_OFF;   /* safe — we're in VBlank */
/* ... VRAM init ... */
DISPLAY_ON;
```
When the display is off, VRAM/OAM/palette RAM are freely accessible without timing concerns.

### VRAM Writes
Always guard VRAM writes with `wait_vbl_done()` **unless display is off** (`DISPLAY_OFF`).
Writing to VRAM outside VBlank (Mode 0/1) causes graphical corruption.
CGB palette RAM (BCPD/OCPD) is also inaccessible during Mode 3.

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
`move_sprite(nb, x, y)` writes raw OAM bytes. Screen pixel = (x − 8, y − 16).
- `DEVICE_SPRITE_PX_OFFSET_X = 8`, `DEVICE_SPRITE_PX_OFFSET_Y = 16`
- **Fully visible bounds (8×8): x ∈ [8, 167], y ∈ [16, 159]**
- Hidden when OAM x ≥ 168 or OAM y = 0 or OAM y ≥ 160 (still count toward 10/scanline limit)
- **Common mistake:** using 152/136 as max — these cut off ~15px of reachable screen area

### CGB Palettes
- Format: 5-bit RGB packed with `RGB(r, g, b)` macro (values 0–31)
- Sprite color index 0 is **always transparent** — usable indices: 1, 2, 3
- All BG tiles default to palette 0 unless you write the attribute map (VRAM bank 1)
- `set_bkg_palette(0, 1, pal)` controls console text color
- Cannot write palette RAM during PPU Mode 3 — always update during VBlank

### 8×16 Sprite Mode
- LCDC bit 2 = 1 enables 8×16; tile index bit 0 is ignored
- Top tile = `tile_id & 0xFE`, bottom tile = `tile_id | 0x01`

---

## Console / Font
- `printf` uses BG tile map (SCRN0) as 20×18 char grid; mapping: `ascii − 0x20 = tile index`
- Default font works without explicit init; use `font_init()` / `font_load()` for multi-font API
- `font_ibm` uses tiles 0–95 — load game BG tiles starting at ID 96+ to avoid overwriting
- `M_NO_SCROLL` wraps cursor instead of scrolling; `M_NO_INTERP` disables special chars

---

## SDCC Gotchas
- **No compound literals**: `(const uint16_t[]){...}` → use named `static const` arrays
- **Warning "conditional flow changed by optimizer: so said EVELYN"** — harmless, not an error
- Prefer `uint8_t` loop counters; avoid `float`/`double`; no `malloc`/`free`
- Large local arrays (>~64 bytes) → stack overflow risk; use `static` or global

---

## Verification
After changes: run `/test` (host-side, gcc) then `/build` (full ROM).
