#include "unity.h"
#include <gb/gb.h>
#include "camera.h"
#include "track.h"

extern int     mock_move_bkg_call_count;
extern uint8_t mock_move_bkg_last_y;
void setUp(void) {
    mock_vram_clear();
    active_map_w = 20u;   /* match old MAP_TILES_W for existing tests */
    active_map_h = 100u;  /* match old MAP_TILES_H for existing tests */
    camera_set_tile_base(0u);  /* raw tile indices in tests — no loader offset */
}
void tearDown(void) {}

/* --- camera_init: cam_y from player world Y ----------------------------- */

/* Player at world y=80: cam_y = max(80-72, 0) = 8 */
void test_camera_init_sets_cam_y(void) {
    camera_init(80, 80);
    TEST_ASSERT_EQUAL_UINT16(8, cam_y);
}

/* --- camera_init: clamp at edges ---------------------------------------- */

/* Player near top: cam_y cannot go negative */
void test_camera_init_clamps_cam_y_to_zero(void) {
    camera_init(80, 40);  /* 40-72 = -32 -> 0 */
    TEST_ASSERT_EQUAL_UINT16(0, cam_y);
}

/* Player past bottom: cam_y capped at CAM_MAX_Y = 672 (100*8 - HUD_SCANLINE=128) */
void test_camera_init_clamps_cam_y_to_max(void) {
    camera_init(80, 800);  /* 800-72=728 > 672 -> 672 */
    TEST_ASSERT_EQUAL_UINT16(672, cam_y);
}

/* --- camera_init: preloads exactly 18 rows, not all 100 ----------------- */

void test_camera_init_preloads_18_rows(void) {
    /* camera_init() uses set_bkg_tiles() directly (display-off direct write).
     * cam_y=8 -> first_row=1; preloads rows 1-18 = 18 set_bkg_tiles calls
     * (one per row, no ring-wrap for 20-tile-wide narrow track). */
    mock_vram_clear();
    active_map_w = 20u;
    active_map_h = 100u;
    camera_init(88, 8);
    /* 18 rows x 1 set_bkg_tiles call each = 18 */
    TEST_ASSERT_EQUAL_INT(18, mock_set_bkg_tiles_call_count);
}

/* --- camera_update: bidirectional centering camera --------------------- */

/* Moving player up decreases cam_y to follow */
void test_camera_update_cam_y_follows_player_up(void) {
    camera_init(80, 80);    /* cam_y = 8 */
    camera_update(80, 40);  /* 40-72=-32 -> clamp 0; cam_y = 0 */
    TEST_ASSERT_EQUAL_UINT16(0, cam_y);
}

/* Bidirectional: moving player DOWN also advances cam_y */
void test_camera_update_cam_y_follows_player_down(void) {
    camera_init(80, 80);     /* cam_y = 8 */
    camera_update(80, 200);  /* ncy = 200-72 = 128; cam_y -> 128 */
    TEST_ASSERT_EQUAL_UINT16(128, cam_y);
}

/* cam_y never goes below 0 even when player is far above top of map */
void test_camera_update_cam_y_clamped_at_zero(void) {
    camera_init(80, 80);    /* cam_y = 8 */
    camera_update(80, 0);   /* ncy=clamp(-72, 656)=0 < cam_y=8 -> cam_y=0 */
    TEST_ASSERT_EQUAL_UINT16(0, cam_y);
}

/* --- camera_update: buffers rows, does NOT write VRAM directly ---------- */

void test_camera_update_does_not_write_vram(void) {
    int count_after_init;
    camera_init(80, 80);
    count_after_init = mock_set_bkg_tiles_call_count;
    camera_update(80, 200);  /* buffers new rows */
    TEST_ASSERT_EQUAL_INT(count_after_init, mock_set_bkg_tiles_call_count);
}

/* --- camera_flush_vram: drains pending row streams --------------------- */

/* Bidirectional: moving player DOWN buffers new bottom row */
void test_camera_update_downward_buffers_bottom_row(void) {
    int count_before;
    camera_init(80, 80);   /* cam_y=8; visible rows 1-18 preloaded */
    count_before = mock_set_bkg_tiles_call_count;
    camera_update(80, 88); /* ncy=16 > cam_y=8 → buffers bottom row 19 */
    camera_flush_vram();
    TEST_ASSERT_GREATER_THAN_INT(count_before, mock_set_bkg_tiles_call_count);
}

/* Crossing tile boundary upward -> flush writes exactly one new top row */
void test_camera_flush_streams_new_top_row(void) {
    int count_after_update;
    /* cam_y=8 -> first_row=1; move up: cam_y=0, old_top=1, new_top=0 */
    camera_init(80, 80);
    camera_update(80, 72);  /* 72-72=0; cam_y->0, buffers row 0 */
    count_after_update = mock_set_bkg_tiles_call_count;
    camera_flush_vram();
    TEST_ASSERT_GREATER_THAN_INT(count_after_update, mock_set_bkg_tiles_call_count);
}

/* Second flush must be a no-op */
void test_camera_flush_clears_buffer(void) {
    int count_after_first;
    camera_init(80, 80);
    camera_update(80, 88);
    camera_flush_vram();
    count_after_first = mock_set_bkg_tiles_call_count;
    camera_flush_vram();
    TEST_ASSERT_EQUAL_INT(count_after_first, mock_set_bkg_tiles_call_count);
}

/* No-op when buffer is empty */
void test_camera_flush_noop_on_empty_buffer(void) {
    camera_init(80, 80);
    mock_set_bkg_tiles_call_count = 0;
    camera_flush_vram();
    TEST_ASSERT_EQUAL_INT(0, mock_set_bkg_tiles_call_count);
}

/* Game restart safety: stale buffer from previous session must not be flushed */
void test_camera_init_clears_stale_stream_buffer(void) {
    int count_after_reinit;
    /* First session: update buffers a row but never flush */
    camera_init(80, 80);   /* cam_y=8, rows 1-18 preloaded */
    camera_update(80, 88); /* cam_y->16, row 19 buffered but NOT flushed */
    /* Second session (game restart) */
    camera_init(80, 80);
    count_after_reinit = mock_set_bkg_tiles_call_count;
    /* Flush must be a no-op — stale row 19 from first session must be gone */
    camera_flush_vram();
    TEST_ASSERT_EQUAL_INT(count_after_reinit, mock_set_bkg_tiles_call_count);
}

/* --- camera_apply_scroll: shadow register (legacy ordering tests updated) */

/* camera_apply_scroll() must update cam_scy_shadow with current cam_y */
void test_camera_apply_scroll_sets_shadow_to_cam_y(void) {
    camera_init(80, 80);           /* cam_y = 8 */
    mock_move_bkg_call_count = 0;
    camera_apply_scroll();
    TEST_ASSERT_EQUAL_UINT8(8u, cam_scy_shadow);
}

/* cam_scy_shadow reflects cam_y at the moment of the call */
void test_camera_apply_scroll_shadow_matches_cam_y(void) {
    camera_init(80, 80);           /* cam_y = 8 */
    camera_apply_scroll();
    TEST_ASSERT_EQUAL_UINT8((uint8_t)cam_y, cam_scy_shadow);
}

/* Ordering: flush must write VRAM before apply_scroll captures cam_y.
 * After update queues a row and flush runs, shadow must reflect new cam_y. */
void test_camera_apply_scroll_reflects_post_flush_cam_y(void) {
    camera_init(80, 80);           /* cam_y = 8 */
    camera_update(80, 72);         /* cam_y -> 0, buffers row 0 */
    camera_flush_vram();           /* writes row 0 to VRAM */
    camera_apply_scroll();
    TEST_ASSERT_EQUAL_UINT8(0u, cam_scy_shadow);
}

/* --- camera_apply_scroll: shadow register (new behaviour) --------------- */

/* camera_apply_scroll() must write cam_y into cam_scy_shadow, not move_bkg.
 * The VBL ISR is responsible for applying the shadow to the hardware register. */
void test_camera_apply_scroll_updates_shadow(void) {
    camera_init(80, 80);   /* cam_y = 8 */
    camera_apply_scroll();
    TEST_ASSERT_EQUAL_UINT8(8u, cam_scy_shadow);
}

/* camera_apply_scroll() must NOT call move_bkg directly — that is the ISR's job. */
void test_camera_apply_scroll_does_not_call_move_bkg(void) {
    camera_init(80, 80);
    mock_move_bkg_call_count = 0;
    camera_apply_scroll();
    TEST_ASSERT_EQUAL_INT(0, mock_move_bkg_call_count);
}

/* ---- cam_x: clamping -------------------------------------------------- */

/* Wide track (64 tiles = 512px): cam_x follows player X, clamped to [0, 352] */
void test_camera_init_sets_cam_x_wide_track(void) {
    active_map_w = 64u;
    active_map_h = 100u;
    camera_init(320, 80);   /* player_x=320: cam_x = 320-80 = 240, within [0,352] */
    TEST_ASSERT_EQUAL_UINT16(240u, cam_x);
}

/* cam_x cannot go negative */
void test_camera_init_clamps_cam_x_to_zero(void) {
    active_map_w = 64u;
    active_map_h = 100u;
    camera_init(40, 80);    /* 40-80 = -40 → clamp 0 */
    TEST_ASSERT_EQUAL_UINT16(0u, cam_x);
}

/* cam_x capped at (active_map_w*8 - 160) */
void test_camera_init_clamps_cam_x_to_max(void) {
    active_map_w = 64u;    /* cam_max_x = 64*8 - 160 = 352 */
    active_map_h = 100u;
    camera_init(600, 80);  /* 600-80=520 > 352 → 352 */
    TEST_ASSERT_EQUAL_UINT16(352u, cam_x);
}

/* Narrow track (20 tiles = 160px): cam_x is always 0 (no horizontal scroll) */
void test_camera_init_cam_x_zero_for_narrow_track(void) {
    active_map_w = 20u;
    active_map_h = 100u;
    camera_init(80, 80);
    TEST_ASSERT_EQUAL_UINT16(0u, cam_x);
}

/* cam_x updates when player moves horizontally */
void test_camera_update_cam_x_follows_player(void) {
    active_map_w = 64u;
    active_map_h = 100u;
    camera_init(200, 80);   /* cam_x = 200-80 = 120 */
    camera_update(300, 80); /* cam_x = 300-80 = 220 */
    TEST_ASSERT_EQUAL_UINT16(220u, cam_x);
}

/* ---- cam_x: column buffer --------------------------------------------- */

/* Crossing X tile boundary right buffers new right column */
void test_camera_update_crossing_x_tile_right_buffers_column(void) {
    int col_count_before;
    active_map_w = 64u;
    active_map_h = 100u;
    /* Start at cam_x=0 (tile boundary 0), move right past tile boundary 1 (8px) */
    camera_init(80, 80);    /* cam_x=0 */
    col_count_before = mock_set_bkg_tiles_call_count;
    camera_update(96, 80);  /* cam_x=16 — crosses tile boundary at x=8 */
    camera_flush_vram();
    /* Must have written at least one new column */
    TEST_ASSERT_GREATER_THAN_INT(col_count_before, mock_set_bkg_tiles_call_count);
}

/* cam_tile_x snapshot is captured at camera_update() time */
void test_camera_update_snapshots_cam_tile_x(void) {
    active_map_w = 64u;
    active_map_h = 100u;
    camera_init(80, 80);   /* cam_x=0, cam_tile_x=0 */
    camera_update(96, 80); /* cam_x=16, cam_tile_x snapshot should be 0→2 transition */
    /* Verify flush does not use a stale cam_tile_x from after update */
    /* (behavioral: flush call count must be > init count, proving column was queued at update time) */
    TEST_ASSERT_EQUAL_UINT16(16u, cam_x);
}

/* ---- camera_invalidate_row -------------------------------------------- */

/* Queuing a row via camera_invalidate_row() then flushing must stream it.
 * Mirrors test_camera_flush_streams_new_top_row spy pattern:
 * capture call count before flush, assert it is greater after. */
void test_camera_invalidate_row_queues_a_row_for_flush(void) {
    int count_after_invalidate;
    camera_init(80, 80);              /* cam_y=8, rows 1-18 preloaded */
    camera_invalidate_row(5u);        /* enqueue world tile row 5 */
    count_after_invalidate = mock_set_bkg_tiles_call_count;
    camera_flush_vram();              /* must drain the queued row */
    TEST_ASSERT_GREATER_THAN_INT(count_after_invalidate, mock_set_bkg_tiles_call_count);
}

/* ---- cam_scx_shadow ---------------------------------------------------- */

/* camera_apply_scroll() sets cam_scx_shadow from cam_x */
void test_camera_apply_scroll_sets_cam_scx_shadow(void) {
    active_map_w = 64u;
    active_map_h = 100u;
    camera_init(200, 80);  /* cam_x = 120 */
    camera_apply_scroll();
    TEST_ASSERT_EQUAL_UINT8((uint8_t)cam_x, cam_scx_shadow);
}

/* ---- camera_invalidate_col / queue-acceptance return codes ------------ */

void test_invalidate_col_streams_that_column(void) {
    /* A vertical beam must be able to repair the column it painted over. */
    camera_init(0, 0);
    camera_flush_vram();          /* drain whatever init queued */
    mock_vram_clear();
    TEST_ASSERT_EQUAL_UINT8(1, camera_invalidate_col(3u));
    camera_flush_vram();
    /* stream_col writes one column: width 1, height VIS_ROWS, at vram x = 3. */
    TEST_ASSERT_EQUAL_UINT8(1,  mock_bkg_last_w);
    TEST_ASSERT_EQUAL_UINT8(3,  mock_bkg_last_x);
    TEST_ASSERT_EQUAL_UINT8(19, mock_bkg_last_h);
}

void test_invalidate_row_reports_acceptance(void) {
    /* The beam retries a dropped restore, so the queue must say whether it took it. */
    camera_init(0, 0);
    camera_flush_vram();                                    /* drain: len == 0 */
    TEST_ASSERT_EQUAL_UINT8(1, camera_invalidate_row(2u));  /* len 0 -> 1 */
    TEST_ASSERT_EQUAL_UINT8(1, camera_invalidate_row(3u));  /* len 1 -> 2 == STREAM_BUF_SIZE */
    TEST_ASSERT_EQUAL_UINT8(0, camera_invalidate_row(4u));  /* full -> refused */
}

/* ---- camera_repair_cells (#582) --------------------------------------- */

/* A 20x16 map of road (tile 1) with one distinctive tile (7) at (11, 9).
 * A repair that writes the wrong cell, or drops the tile base, cannot pass. */
static uint8_t s_repair_map[20u * 16u];

/* Leaves track.c pointing at s_repair_map and active_map_h at 16. setUp()
 * restores active_map_h but not the map pointer, so any test added AFTER the
 * repair tests must call track_test_set_map() itself before camera_init(). */
static void repair_map_init(void) {
    uint16_t i;
    for (i = 0u; i < 20u * 16u; i++) s_repair_map[i] = 1u;
    s_repair_map[(9u * 20u) + 11u] = 7u;
    track_test_set_map(s_repair_map, 20u, 16u);
    camera_init(0, 0);        /* 20x16 map -> cam_x = cam_y = 0, both clamped */
    camera_flush_vram();      /* drain whatever init queued */
    mock_vram_clear();
}

void test_repair_cells_repaints_the_track_row(void) {
    repair_map_init();
    camera_repair_cells(10u, 9u, 2u, 0u);
    TEST_ASSERT_EQUAL_UINT8(1u, mock_vram[(9u * 32u) + 10u]);
    TEST_ASSERT_EQUAL_UINT8(7u, mock_vram[(9u * 32u) + 11u]);
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[(9u * 32u) + 12u]);   /* outside the run */
}

void test_repair_cells_adds_the_track_tile_base(void) {
    repair_map_init();
    camera_set_tile_base(0x20u);
    camera_repair_cells(11u, 9u, 1u, 0u);
    TEST_ASSERT_EQUAL_UINT8(0x27u, mock_vram[(9u * 32u) + 11u]);
}

void test_repair_cells_repaints_a_track_column(void) {
    repair_map_init();
    camera_repair_cells(11u, 8u, 2u, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, mock_vram[(8u * 32u) + 11u]);
    TEST_ASSERT_EQUAL_UINT8(7u, mock_vram[(9u * 32u) + 11u]);
}

void test_repair_cells_clamps_the_count(void) {
    repair_map_init();
    camera_repair_cells(0u, 9u, (uint8_t)(CAMERA_REPAIR_MAX_CELLS + 2u), 0u);
    TEST_ASSERT_EQUAL_INT((int)CAMERA_REPAIR_MAX_CELLS, mock_set_bkg_tiles_call_count);
    TEST_ASSERT_EQUAL_UINT8(1u, mock_vram[(9u * 32u) + (CAMERA_REPAIR_MAX_CELLS - 1u)]);
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[(9u * 32u) + CAMERA_REPAIR_MAX_CELLS]);
}

/* ---- Streaming coverage fixture (#752) --------------------------------- */

/* 48x40 tiles: wide enough for cam_x to reach tile 20 (cam_max_x = 48*8-160 =
 * 224) and tall enough for cam_y to reach tile 20 (cam_max_y = 40*8-128 = 192).
 * At tile 20 the 22-column window (20+22 = 42 > 32) and the 19-row window
 * (20+19 = 39 > 32) each cross the 32-tile BG ring boundary.
 *
 * Every cell holds a value in 1..127, distinct from its neighbours on both
 * axes, so a cell assertion catches an off-by-one in either direction. Never 0,
 * so "this cell was not written" (mock_vram_clear leaves 0) can never be
 * confused with "this cell holds tile 0". Never above 127, so adding
 * STREAM_TILE_BASE cannot wrap a uint8_t. */
#define BIGMAP_W 48u
#define BIGMAP_H 40u
#define STREAM_TILE_BASE 0x20u

static uint8_t s_big_map[BIGMAP_W * BIGMAP_H];

static uint8_t big_map_tile(uint8_t tx, uint8_t ty) {
    return (uint8_t)(1u + (((uint16_t)ty * 7u + (uint16_t)tx) % 127u));
}

/* Installs the 48x40 map. Does NOT call camera_init() — the direct-write tests
 * need the tile base set before init, the streaming tests need it set after. */
static void big_map_install(void) {
    uint16_t tx, ty;
    for (ty = 0u; ty < BIGMAP_H; ty++) {
        for (tx = 0u; tx < BIGMAP_W; tx++) {
            s_big_map[(ty * BIGMAP_W) + tx] = big_map_tile((uint8_t)tx, (uint8_t)ty);
        }
    }
    track_test_set_map(s_big_map, (uint8_t)BIGMAP_W, (uint8_t)BIGMAP_H);
}

/* The cell assertions below are only as strong as the fixture is varied: if
 * big_map_tile() ever collapsed to a constant, every one of them would pass
 * against the wrong cell. Pin the distinctness the other tests rely on. */
void test_big_map_fixture_tiles_are_distinct(void) {
    TEST_ASSERT_NOT_EQUAL_UINT8(big_map_tile(20u, 5u), big_map_tile(21u, 5u));
    TEST_ASSERT_NOT_EQUAL_UINT8(big_map_tile(31u, 5u), big_map_tile(32u, 5u));
    TEST_ASSERT_NOT_EQUAL_UINT8(big_map_tile(3u, 20u), big_map_tile(3u, 21u));
    TEST_ASSERT_NOT_EQUAL_UINT8(big_map_tile(3u, 31u), big_map_tile(3u, 32u));
    TEST_ASSERT_NOT_EQUAL_UINT8(0u, big_map_tile(3u, 36u));
}

/* ---- stream_row: tile base and ring-wrap split (#752) ------------------ */

/* Camera at cam_x = 0 -> vram_x = 0, so the 22-column window does NOT cross the
 * ring boundary. With a non-zero tile base every written cell must carry the
 * offset, and cells past the window must stay untouched. */
void test_stream_row_adds_the_tile_base(void) {
    big_map_install();
    camera_init(80, 72);            /* cam_x = 0, cam_y = 0 */
    camera_flush_vram();            /* drain whatever init queued */
    mock_vram_clear();
    camera_set_tile_base(STREAM_TILE_BASE);
    TEST_ASSERT_EQUAL_UINT8(1u, camera_invalidate_row(5u));
    camera_flush_vram();
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(big_map_tile(0u, 5u) + STREAM_TILE_BASE),
                            mock_vram[(5u * 32u) + 0u]);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(big_map_tile(10u, 5u) + STREAM_TILE_BASE),
                            mock_vram[(5u * 32u) + 10u]);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(big_map_tile(21u, 5u) + STREAM_TILE_BASE),
                            mock_vram[(5u * 32u) + 21u]);
    /* One past the 22-column window: the row must not have been split. */
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[(5u * 32u) + 22u]);
}

/* Camera at cam_x = 160 -> cam_tile_x = 20, vram_x = 20, 20 + 22 = 42 > 32.
 * first_count = 12: cells x = 20..31 come from map columns 20..31, and the
 * wrapped cells x = 0..9 come from map columns 32..41. */
void test_stream_row_splits_at_the_bg_ring_boundary(void) {
    big_map_install();
    camera_init(240, 72);           /* cam_x = 160, cam_y = 0 */
    camera_flush_vram();
    mock_vram_clear();
    TEST_ASSERT_EQUAL_UINT8(1u, camera_invalidate_row(5u));
    camera_flush_vram();
    /* First half — the end of the BG row. */
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(20u, 5u), mock_vram[(5u * 32u) + 20u]);
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(31u, 5u), mock_vram[(5u * 32u) + 31u]);
    /* Second half — wrapped to VRAM x = 0. */
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(32u, 5u), mock_vram[(5u * 32u) + 0u]);
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(41u, 5u), mock_vram[(5u * 32u) + 9u]);
    /* The gap between the two halves must stay untouched. */
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[(5u * 32u) + 10u]);
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[(5u * 32u) + 19u]);
}

/* ---- stream_col: tile base and ring-wrap split (#752) ------------------ */

/* Camera at cam_y = 0 -> vram_y = 0, so the 19-row window does NOT cross the
 * ring boundary. With a non-zero tile base every written cell must carry the
 * offset, and cells past the window must stay untouched. */
void test_stream_col_adds_the_tile_base(void) {
    big_map_install();
    camera_init(80, 72);            /* cam_x = 0, cam_y = 0 */
    camera_flush_vram();
    mock_vram_clear();
    camera_set_tile_base(STREAM_TILE_BASE);
    TEST_ASSERT_EQUAL_UINT8(1u, camera_invalidate_col(3u));
    camera_flush_vram();
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(big_map_tile(3u, 0u) + STREAM_TILE_BASE),
                            mock_vram[(0u * 32u) + 3u]);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(big_map_tile(3u, 9u) + STREAM_TILE_BASE),
                            mock_vram[(9u * 32u) + 3u]);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(big_map_tile(3u, 18u) + STREAM_TILE_BASE),
                            mock_vram[(18u * 32u) + 3u]);
    /* One past the 19-row window: the column must not have been split. */
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[(19u * 32u) + 3u]);
}

/* Camera at cam_y = 160 -> cam_tile_y = 20, vram_y = 20, 20 + 19 = 39 > 32.
 * first_count = 12: cells y = 20..31 come from map rows 20..31, and the wrapped
 * cells y = 0..6 come from map rows 32..38. */
void test_stream_col_splits_at_the_bg_ring_boundary(void) {
    big_map_install();
    camera_init(80, 232);           /* cam_x = 0, cam_y = 160 */
    camera_flush_vram();
    mock_vram_clear();
    TEST_ASSERT_EQUAL_UINT8(1u, camera_invalidate_col(3u));
    camera_flush_vram();
    /* First half — the bottom of the BG column. */
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(3u, 20u), mock_vram[(20u * 32u) + 3u]);
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(3u, 31u), mock_vram[(31u * 32u) + 3u]);
    /* Second half — wrapped to VRAM y = 0. */
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(3u, 32u), mock_vram[(0u * 32u) + 3u]);
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(3u, 38u), mock_vram[(6u * 32u) + 3u]);
    /* The gap between the two halves must stay untouched. */
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[(7u * 32u) + 3u]);
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[(19u * 32u) + 3u]);
}

/* ---- stream_row_direct: the camera_init display-off path (#752) -------- */

/* camera_init() preloads 18 rows through stream_row_direct(). The tile base
 * must be set BEFORE init, because init is the only caller of that path.
 * cam_x = 0 -> vram_x = 0, so no row is split here. */
void test_stream_row_direct_adds_the_tile_base(void) {
    big_map_install();
    mock_vram_clear();
    camera_set_tile_base(STREAM_TILE_BASE);
    camera_init(80, 72);            /* cam_x = 0, cam_y = 0 -> preloads rows 0..17 */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(big_map_tile(0u, 0u) + STREAM_TILE_BASE),
                            mock_vram[(0u * 32u) + 0u]);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(big_map_tile(21u, 0u) + STREAM_TILE_BASE),
                            mock_vram[(0u * 32u) + 21u]);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(big_map_tile(7u, 17u) + STREAM_TILE_BASE),
                            mock_vram[(17u * 32u) + 7u]);
    /* One past the 22-column window: no row was split. */
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[(0u * 32u) + 22u]);
}

/* Camera at cam_x = 160 -> vram_x = 20 for every preloaded row, so each of the
 * 18 rows stream_row_direct() writes is split at the ring boundary. */
void test_stream_row_direct_splits_at_the_bg_ring_boundary(void) {
    big_map_install();
    mock_vram_clear();
    camera_init(240, 72);           /* cam_x = 160, cam_y = 0 -> preloads rows 0..17 */
    /* First half — the end of the BG row. */
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(20u, 3u), mock_vram[(3u * 32u) + 20u]);
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(31u, 3u), mock_vram[(3u * 32u) + 31u]);
    /* Second half — wrapped to VRAM x = 0. */
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(32u, 3u), mock_vram[(3u * 32u) + 0u]);
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(41u, 3u), mock_vram[(3u * 32u) + 9u]);
    /* The gap between the two halves must stay untouched. */
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[(3u * 32u) + 10u]);
    /* A second preloaded row is split the same way. */
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(20u, 12u), mock_vram[(12u * 32u) + 20u]);
    TEST_ASSERT_EQUAL_UINT8(big_map_tile(32u, 12u), mock_vram[(12u * 32u) + 0u]);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_camera_init_sets_cam_y);
    RUN_TEST(test_camera_init_clamps_cam_y_to_zero);
    RUN_TEST(test_camera_init_clamps_cam_y_to_max);
    RUN_TEST(test_camera_init_preloads_18_rows);
    RUN_TEST(test_camera_update_cam_y_follows_player_up);
    RUN_TEST(test_camera_update_cam_y_follows_player_down);
    RUN_TEST(test_camera_update_cam_y_clamped_at_zero);
    RUN_TEST(test_camera_update_does_not_write_vram);
    RUN_TEST(test_camera_update_downward_buffers_bottom_row);
    RUN_TEST(test_camera_flush_streams_new_top_row);
    RUN_TEST(test_camera_flush_clears_buffer);
    RUN_TEST(test_camera_flush_noop_on_empty_buffer);
    RUN_TEST(test_camera_init_clears_stale_stream_buffer);
    RUN_TEST(test_camera_apply_scroll_sets_shadow_to_cam_y);
    RUN_TEST(test_camera_apply_scroll_shadow_matches_cam_y);
    RUN_TEST(test_camera_apply_scroll_reflects_post_flush_cam_y);
    RUN_TEST(test_camera_apply_scroll_updates_shadow);
    RUN_TEST(test_camera_apply_scroll_does_not_call_move_bkg);
    RUN_TEST(test_camera_init_sets_cam_x_wide_track);
    RUN_TEST(test_camera_init_clamps_cam_x_to_zero);
    RUN_TEST(test_camera_init_clamps_cam_x_to_max);
    RUN_TEST(test_camera_init_cam_x_zero_for_narrow_track);
    RUN_TEST(test_camera_update_cam_x_follows_player);
    RUN_TEST(test_camera_update_crossing_x_tile_right_buffers_column);
    RUN_TEST(test_camera_update_snapshots_cam_tile_x);
    RUN_TEST(test_camera_apply_scroll_sets_cam_scx_shadow);
    RUN_TEST(test_camera_invalidate_row_queues_a_row_for_flush);
    RUN_TEST(test_invalidate_col_streams_that_column);
    RUN_TEST(test_invalidate_row_reports_acceptance);
    RUN_TEST(test_repair_cells_repaints_the_track_row);
    RUN_TEST(test_repair_cells_adds_the_track_tile_base);
    RUN_TEST(test_repair_cells_repaints_a_track_column);
    RUN_TEST(test_repair_cells_clamps_the_count);
    RUN_TEST(test_big_map_fixture_tiles_are_distinct);
    RUN_TEST(test_stream_row_adds_the_tile_base);
    RUN_TEST(test_stream_row_splits_at_the_bg_ring_boundary);
    RUN_TEST(test_stream_col_adds_the_tile_base);
    RUN_TEST(test_stream_col_splits_at_the_bg_ring_boundary);
    RUN_TEST(test_stream_row_direct_adds_the_tile_base);
    RUN_TEST(test_stream_row_direct_splits_at_the_bg_ring_boundary);
    return UNITY_END();
}
