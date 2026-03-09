# Design: VBlank Frame Order Fix

**Date:** 2026-03-09
**Issue:** #11 — Bug: game slows down over time during play

## Root Cause

`set_bkg_tiles()` and `set_win_tiles()` in GBDK 2020 use a per-byte `WAIT_STAT` spin loop
(confirmed from `gbdk-lib/libc/targets/sm83/set_xy_t.s`). Each tile byte written when the
PPU is in Mode 2 (OAM scan) or Mode 3 (drawing) stalls until the next HBlank window
(~87–204 dots, ~20–49 µs). Writing 12 tiles (`set_win_tiles(0,0,12,1,...)`) outside VBlank
requires catching 12 separate HBlank windows — up to 12 scanlines of extra latency per frame.

The current frame loop calls game logic *before* VRAM writes:

```c
wait_vbl_done();          // VBlank starts here (~1.087 ms window)
player_update(joypad()); // burns VBlank budget
camera_update(...);      // may also burn it
player_render();         // set_win_tiles — now in active display → WAIT_STAT stalls
```

Because each frame's VRAM write starts later (logic burned more of VBlank), each frame
incurs more HBlank stalls. The extra stall time pushes the next `wait_vbl_done()` call
further back — compounding each frame. Progressive slowdown to a complete halt results,
even when the player is standing still (the `set_win_tiles` debug overlay fires every frame).

## Design

### Frame Loop Structure (main.c)

Swap the render and logic phases so all VRAM writes land immediately after `wait_vbl_done()`:

```c
while (1) {
    wait_vbl_done();
    // Phase 1: VRAM writes — inside VBlank window
    player_render();          // move_sprite (OAM shadow) + set_win_tiles
    camera_flush_vram();      // set_bkg_tiles for buffered streams
    move_bkg(cam_x, cam_y);   // SCX/SCY sync with just-flushed tiles
    // Phase 2: Game logic — runs during active display
    player_update(joypad());
    camera_update(...);       // computes new scroll, buffers tile streams
}
```

### Camera Split (camera.c)

`camera_update()` is split into two responsibilities:

- **Compute phase** (runs during active display): detect tile boundary crossings, record
  which columns/rows need streaming into a small pending-stream buffer. Update `cam_x`/`cam_y`.
  Do NOT call `set_bkg_tiles()` directly.

- **Flush phase** (`camera_flush_vram()`, called at VBlank start): drain the pending-stream
  buffer, executing the deferred `set_bkg_tiles()` calls while VRAM is accessible.

Pending stream buffer: up to 4 entries `{ uint8_t index; uint8_t is_row; }`. In practice at
most 2 trigger per frame (one column + one row axis). The one-frame lag on newly-revealed
tile columns is visually undetectable at 1px/frame scroll speed.

`move_bkg()` is removed from `camera_update()` and called explicitly in the VBlank phase of
`main.c`, synchronised with the tile flush.

### VBlank Budget

| Write | Bytes | Cost in VBlank (~0 wait) |
|-------|-------|--------------------------|
| `set_win_tiles(0,0,12,1,...)` | 12 | ~48 cycles |
| `stream_column` worst case (36 bytes) | 36 | ~144 cycles |
| `stream_row` worst case (40 bytes) | 40 | ~160 cycles |
| **Total worst case** | **88** | **~352 cycles ≪ 4,560 dots** |

All writes fit comfortably within VBlank. No HBlank DMA needed.

## Affected Files

- `src/main.c` — swap render/logic order; call `camera_flush_vram()` and `move_bkg()` in
  VBlank phase; pass cam coords to render separately
- `src/camera.c` — add `camera_flush_vram()`, add pending-stream buffer, remove
  `set_bkg_tiles()` and `move_bkg()` from `camera_update()`
- `src/camera.h` — add `camera_flush_vram()` declaration

## Testing

- Unit tests: `camera_update()` with mocked `set_bkg_tiles` verifies streams are buffered
  (not written immediately); `camera_flush_vram()` verifies buffer is drained and cleared
- Emulator smoketest: run extended play session in mgba-qt; frame rate must remain stable
