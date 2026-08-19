---
summary: camera.c background streaming — camera_invalidate_row/col queue with acceptance return codes, STREAM_BUF_SIZE caps vs camera_update's per-axis cap, camera_repair_cells synchronous BG repair, camera_flush_vram, mock_bkg
tags: [camera, streaming, bg-tiles, vram, vblank, gbdk]
---

# Camera & background streaming

`camera.c` (`#pragma bank 255`) owns scrolling and BG tile streaming. Two repair
mechanisms exist: the **async invalidate queue** and the **synchronous small-range
repair**. The [[beam-laser-module]] and [[beam-trail-repair]] are the main external
consumers.

## camera_invalidate_row/col — queue with acceptance return codes (#430 Task 2)

`camera_invalidate_col()` was added alongside the existing `camera_invalidate_row()`,
and both `BANKED` fns were widened from `void` to `uint8_t`: `return 1u` if the event
was appended to `stream_row_buf`/`stream_col_buf` (guard `< STREAM_BUF_SIZE`, which is
2 — NOT the same cap as `camera_update()`'s own `< 1u` per-axis cap), `return 0u` if
the buffer was already full and the caller must retry next frame. No SDCC gotcha:
widening a `BANKED` fn's return type from `void`→`uint8_t` is just what goes in the A
register before `ret far` — other `BANKED` fns already return `uint8_t`
(`track_tile_type_from_index`), so the autobank trampoline needs no changes.
`camera_invalidate_col` reuses the already-proven `stream_col_buf`→`stream_col()`
consumer path (the same one `camera_update()`'s X-axis branch already drives) — not a
new mechanism, a second producer into an existing one.

Discarding a `BANKED` fn's return value at a bare-statement call site
(`state_playing.c:154`, unchanged) is NOT a `-Wall -Wextra` warning in this codebase's
build flags — confirmed by a clean `make` after the widen; no `(void)` cast needed
anywhere the return is ignored.

**Queue-capacity asymmetry that bites callers:** `camera_update()` only appends a
stream event while its buffer is `< 1u` (camera.c:160,167) whereas
`camera_invalidate_row/col` use the full `STREAM_BUF_SIZE=2` — queueing an external
repair first makes the camera silently drop its own row stream and leave an unpainted
row while scrolling. That is why `beam_update()` must run AFTER `camera_update()` (see
[[beam-laser-module]]) and why nothing may queue invalidates during the render phase
(src/camera.h:53, see [[beam-trail-repair]]). `camera_flush_vram()` zeroes both queue
lengths every render phase, so a full buffer self-heals next frame.

**Mock support:** `mock_bkg_last_x/y/w/h` added to `tests/mocks/mock_bkg.c` (set at the
top of `set_bkg_tiles()`, zeroed in `mock_vram_clear()`) + declared `extern` in
`tests/mocks/gb/gb.h` — lets a test tell a row stream (`w=VIS_COLS,h=1`) apart from a
column stream (`w=1,h=VIS_ROWS`) without decoding tile content. There is no
`mock_bkg.h` — `mock_vram`/`mock_vram_clear()` are declared in `tests/mocks/gb/gb.h`.

**Test hazard:** `tests/test_camera.c` never calls `track_test_set_map`; injecting a
small map there would leave the active-map pointer dangling for every later test (each
`setUp` only resets `active_map_w/h`, not the map pointer) — the col/row-acceptance
tests deliberately avoid it. Same dangling-pointer family as [[host-test-gotchas]].
test_camera went 27→29 tests.

## camera_repair_cells — synchronous small-range BG repair (#582 Task 1)

`camera_repair_cells(tx, ty, count, vertical)` is the synchronous sibling to the async
`camera_invalidate_row/col` queue. Added to `camera.c` (existing manifest entry — no
new `.c` file). Unlike the queue, it writes VRAM **immediately** via `set_bkg_tiles()`
(one call per cell, up to `CAMERA_REPAIR_MAX_CELLS=4u`) and must NOT call
`camera_invalidate_row/col` — it is VBlank-phase-only, not a queue producer.
`static uint8_t repair_buf[CAMERA_REPAIR_MAX_CELLS]` is a tiny module-static buffer
(not local/stack), reused via `track_fill_row_range`/`track_fill_col` exactly like
`stream_row`/`stream_col` already do.

**The clamp on `count` MUST run BEFORE the `track_fill_*` call** — `repair_buf` is
exactly `CAMERA_REPAIR_MAX_CELLS` bytes and `track_fill_row_range`/`track_fill_col`
write `count` of them uninspected; clamping after the fill overflows the static buffer
instead of failing a test cleanly. One `set_bkg_tiles()` call per cell (not one batched
call for the whole run) is REQUIRED, not an oversight — a host test asserts the exact
call count equals the (clamped) cell count, specifically to catch an implementation
that batches or ignores the cap. Generalizes cleanly: takes an arbitrary start cell,
count, and axis, so a second caller (the beam-repair tasks in #582 — see
[[beam-trail-repair]]) needs no change to this function.
