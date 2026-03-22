#include "unity.h"
#include <gb/gb.h>
#include "camera.h"
#include "track.h"

extern int     mock_move_bkg_call_count;
extern uint8_t mock_move_bkg_last_y;

void setUp(void)    { mock_vram_clear(); }
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

/* Player past bottom: cam_y capped at CAM_MAX_Y = 656 */
void test_camera_init_clamps_cam_y_to_max(void) {
    camera_init(80, 800);  /* 800-72=728 > 656 -> 656 */
    TEST_ASSERT_EQUAL_UINT16(656, cam_y);
}

/* --- camera_init: preloads exactly 18 rows, not all 100 ----------------- */

void test_camera_init_preloads_18_rows(void) {
    /* cam_y=8 -> first_row=1; preloads rows 1-18 = 18 set_bkg_tiles calls */
    camera_init(80, 80);
    TEST_ASSERT_EQUAL_INT(18, mock_set_bkg_tiles_call_count);
}

/* --- camera_update: bidirectional centering camera --------------------- */

/* Moving player up decreases cam_y to follow */
void test_camera_update_cam_y_follows_player_up(void) {
    camera_init(80, 80);    /* cam_y = 8 */
    camera_update(80, 40);  /* 40-72=-32 -> clamp 0; cam_y = 0 */
    TEST_ASSERT_EQUAL_UINT16(0, cam_y);
}

/* Upward-only: moving player down must NOT advance cam_y */
void test_camera_update_cam_y_does_not_advance_downward(void) {
    camera_init(80, 80);     /* cam_y = 8 */
    camera_update(80, 200);  /* ncy=128 >= cam_y=8 -> no-op */
    TEST_ASSERT_EQUAL_UINT16(8, cam_y);
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

/* Downward player movement must NOT buffer any rows (upward-only scroll) */
void test_camera_update_downward_does_not_buffer_rows(void) {
    int count_after_init;
    camera_init(80, 80);
    count_after_init = mock_set_bkg_tiles_call_count;
    camera_update(80, 88);   /* ncy=16 >= cam_y=8 -> no-op */
    camera_flush_vram();
    TEST_ASSERT_EQUAL_INT(count_after_init, mock_set_bkg_tiles_call_count);
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

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_camera_init_sets_cam_y);
    RUN_TEST(test_camera_init_clamps_cam_y_to_zero);
    RUN_TEST(test_camera_init_clamps_cam_y_to_max);
    RUN_TEST(test_camera_init_preloads_18_rows);
    RUN_TEST(test_camera_update_cam_y_follows_player_up);
    RUN_TEST(test_camera_update_cam_y_does_not_advance_downward);
    RUN_TEST(test_camera_update_cam_y_clamped_at_zero);
    RUN_TEST(test_camera_update_does_not_write_vram);
    RUN_TEST(test_camera_update_downward_does_not_buffer_rows);
    RUN_TEST(test_camera_flush_streams_new_top_row);
    RUN_TEST(test_camera_flush_clears_buffer);
    RUN_TEST(test_camera_flush_noop_on_empty_buffer);
    RUN_TEST(test_camera_init_clears_stale_stream_buffer);
    RUN_TEST(test_camera_apply_scroll_sets_shadow_to_cam_y);
    RUN_TEST(test_camera_apply_scroll_shadow_matches_cam_y);
    RUN_TEST(test_camera_apply_scroll_reflects_post_flush_cam_y);
    RUN_TEST(test_camera_apply_scroll_updates_shadow);
    RUN_TEST(test_camera_apply_scroll_does_not_call_move_bkg);
    return UNITY_END();
}
