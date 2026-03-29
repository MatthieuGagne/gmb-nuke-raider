# Game Boy Development — The Basics

## The Game Boy is a tiny, ancient computer

It has a tiny CPU (the SM83, similar to a Z80), very little memory, and a small LCD screen. Everything is constrained. Every byte matters.

---

## Memory areas

The Game Boy has several distinct memory regions, each with a specific job.

### WRAM (Work RAM) — 8 KB

This is your scratchpad. Variables, game state, arrays — anything your C code needs at runtime lives here. 8 KB sounds tiny because it is. If you declare a large array as a local variable inside a function, it goes on the **stack** (which is inside WRAM) and you'll overflow it. That's why large arrays must be `static` or global.

### VRAM (Video RAM) — 8 KB (or 16 KB on GBC)

This is where **tile graphics data** lives. The screen doesn't show pixels directly — it shows **tiles**. A tile is an 8×8 pixel block. You load your sprite/background images into VRAM as tiles, and the hardware draws them. The catch: **you can only safely write to VRAM during VBlank** (see below). Write during the wrong time and you get garbage on screen.

### OAM (Object Attribute Memory) — 160 bytes

This tiny region holds info about **sprites** (moving objects — player, enemies, bullets). Each sprite entry is 4 bytes: Y position, X position, tile number, and flags (flip, palette). You get **40 sprite slots total**.

### ROM (Read-Only Memory) — the cartridge itself

Your compiled code and all assets (tiles, music) live here. You can't write to it. It's split into **banks** (see below).

---

## The screen and VBlank

The Game Boy screen is drawn **line by line**, top to bottom, 60 times per second. The LCD beam scans across each row. After it finishes the last row, there's a brief gap before it starts the next frame — that gap is called **VBlank** (Vertical Blank).

**VBlank is sacred.** It's the only safe window to update VRAM and OAM, because the LCD hardware isn't reading them. If you write outside VBlank, you're changing memory the hardware is actively reading, and you get visual glitches.

`wait_vbl_done()` in GBDK pauses your code until VBlank starts. The game loop calls it every frame to sync to 60fps and keep writes safe.

---

## ISR (Interrupt Service Routine)

An **interrupt** is the hardware tapping your CPU on the shoulder mid-frame and saying "hey, something happened, deal with it now."

The Game Boy can interrupt for several reasons:

| Interrupt | When it fires |
|-----------|--------------|
| VBlank    | Screen finished drawing a frame |
| Timer     | A hardware timer ticked |
| Joypad    | A button was pressed |
| LCD stat  | The screen hit a specific scanline |

An **ISR** is the function that runs when an interrupt fires. It must be fast (you're stealing CPU time from the main loop) and must not touch things that aren't interrupt-safe.

VBlank ISRs are commonly used to do safe VRAM updates every frame automatically, rather than polling `wait_vbl_done()` in a loop.

---

## Tiles and Sprites

- **Tile**: an 8×8 block of pixels, stored in VRAM. Tiles are the atoms of all Game Boy graphics — backgrounds and sprites are both made of tiles.
- **Background**: a grid of tiles (32×32 = 256×256 pixels) that scrolls. Your map is drawn here.
- **Sprite**: a movable object composed of one or more tiles, rendered via OAM. Hardware draws them on top of the background automatically.

---

## ROM Banking

512 KB doesn't fit in the CPU's address space at once (it only sees 16 KB of ROM at a time). So the cartridge has an **MBC (Memory Bank Controller)** chip that lets you swap in different 16 KB chunks ("banks") of ROM on demand.

- **Bank 0** is always visible. Put your core game loop and frequently-called code here.
- **Banks 1–31** are swappable. Assets (tile data, music) go here.
- Before calling code or reading data in a non-zero bank, you must switch to that bank first.

---

## How a frame works (the game loop)

```
1. wait_vbl_done()        ← sync to VBlank (safe VRAM window)
2. joypad()               ← read button state
3. dispatch game state    ← run the right update function
4. go back to 1
```

Everything — physics, input, rendering — must finish within one frame (~16ms at 60fps). If you're too slow, frames drop and the game stutters.

---

## Summary table

| Region | Size      | What lives here              | Constraint                        |
|--------|-----------|------------------------------|-----------------------------------|
| WRAM   | 8 KB      | Variables, game state        | No large locals (stack overflow)  |
| VRAM   | 8–16 KB   | Tile/sprite graphics data    | Write during VBlank only          |
| OAM    | 160 bytes | Sprite positions & flags     | 40 sprites max                    |
| ROM    | up to 512 KB | Code & assets              | Banked; bank 0 always visible     |
