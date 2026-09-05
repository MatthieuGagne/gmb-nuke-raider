# GBDK common bugs

Read by the `gbdk-expert` agent — the project's catalogue of recurring GBDK/SDCC bugs, one line
each (symptom → fix), read before writing or debugging any `src/*.c`.

Distinct hazards — do not collapse.

- VRAM write outside VBlank → graphical corruption. Always gate VRAM writes behind `wait_vbl_done()` or VBlank ISR.
- Sprites invisible → forgot `SPRITES_8x8` / `SPRITES_8x16` mode before using sprites.
- MBC bank switching questions → use the `bank-pre-write` skill and the automatic post-build gates.
- Wrong sprite tile → `set_sprite_tile()` index is the absolute OBJ-data tile number, not relative.
- **BANKED missing on autobank fn called from bank 0** → direct `call _fn`, wrong bank, crash. Any `#pragma bank 255` fn called from bank-0 code needs `BANKED` on both `.h` decl and `.c` def; header must `#include <gb/gb.h>`. `static` fns must NOT be `BANKED`. Canonical: `src/player.h`. Mock defines `BANKED` empty so host tests compile.
- **Banked module calls `set_sprite_data`/`set_bkg_data` directly** → needs `SWITCH_ROM`, which unmaps the running bank → crash. Route all VRAM tile loading through `loader_load_state()` (NONBANKED bank 0); module inits take a `uint8_t tile_base` (from `loader_get_slot(TILE_ASSET_X)`) and call `set_sprite_tile(id, tile_base+off)` only. Never call `set_sprite_data`/`set_bkg_data` from a `#pragma bank 255` file.
- **BANKED fn reads ROM data in a different bank → silent corruption** (no crash). Route all cross-bank ROM reads through a NONBANKED bank-0 helper that does `SWITCH_ROM / read / SWITCH_ROM(saved)` (e.g. `loader_map_read_byte`, `loader_map_fill_row` in `src/loader.c`). BANKED fns CAN safely call NONBANKED helpers. Never deref a ROM pointer in a BANKED fn if the data may live in a different autobank.
- **`cls()` corrupts track tilemap** → writes all 32 BG rows; `camera_init()` restores only 0–17, leaving 18–31 corrupt (breaks finish/checkpoint detection). Never `cls()` before `state_playing`; clear text rows 0–17 with a `set_bkg_tile_xy` loop using tile `0x00u` (NOT `0x20u` — GBDK maps ASCII space to tile 0x00, so 0x20 renders '@').
- **Large VRAM loop in `update()` → spurious VBlank → `KEY_TICKED` always false.** Full-screen clear (18×20=360 calls) spans >1 frame; the extra VBlank runs `input_update()` twice, overwriting `prev_input`. Full BG clears go in `enter()` under `DISPLAY_OFF`; `update()` redraws only changed cells. Diagnose: if `input`==`prev_input`==pressed value after a press, it ran twice.
- **`state_replace()` instead of `state_pop()` returning from a pushed state** → with `STACK_MAX=2`, `[overmap,playing]` + `state_replace(&overmap)` → `[overmap,overmap]`; next `state_push` silently fails. Pushed states must return via `state_pop()`; only the root title→overmap transition uses `state_replace`.
- **`(uint8_t)(n << 3u)` overflows for n ≥ 32 → wrong array slot** (256&0xFF=0). Use `((uint16_t)n << 3u)` when the array has >32 entries (e.g. `TRACK_TILE_LUT_LEN=47`). gb-c-optimizer may push uint8_t casts — verify the value range first.
- **`<<` lower precedence than `+`** → `(uint16_t)tile_idx << 3u + oy` parses as `<< (3+oy)`. Always parenthesize: `((uint16_t)tile_idx << 3u) + oy`.
- **Chaining two BANKED calls in a ternary → silent register corruption.** SDCC passes the first call's return register straight into the second; the trampoline clobbers it → garbage arg (e.g. `track_tile_type_from_index` returns `TILE_WALL` for road). Adding `EMU_printf` masks it (changes stack frame). Fix: use if/else, never a ternary, when feeding a BANKED return value into another BANKED call.
- **BG tilemap garbled → must call `camera_set_tile_base()`.** `track_fill_*` return raw 0-based tile indices, but the loader puts TILE_ASSET_TRACK at slot 143; without the base, entries point at the font (tiles 0–127). Call `camera_set_tile_base(loader_get_slot(TILE_ASSET_TRACK))` before `camera_init()` in `state_playing.enter()`. Any module writing raw tile indices to BG needs the same base.
- **`set_bkg_attributes(palette 0)` on track BG rows → overlay text invisible.** `camera_init`'s `stream_row_direct` already sets a palette that makes font digits readable; overwriting it with palette 0 can hide them. Don't call `set_bkg_attributes` for overlay tiles on track rows — let the camera's track palette apply.
