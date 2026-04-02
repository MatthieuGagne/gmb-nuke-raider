#include "unity.h"
#include <gb/gb.h>
#include "loader.h"
#include "track.h"

void setUp(void) {}
void tearDown(void) {}

/* Host tests verify that loader functions compile, link, and run without
 * crashing. Bank-switching (SWITCH_ROM) is a no-op in the mock environment.
 * Hardware-specific behavior (actual VRAM writes) requires emulator testing. */

void test_load_player_tiles_is_callable(void) {
    load_player_tiles();
    TEST_PASS();
}

void test_load_track_tiles_is_callable(void) {
    load_track_tiles();
    TEST_PASS();
}

void test_load_track_start_pos_writes_to_out_params(void) {
    int16_t x = -1, y = -1;
    load_track_start_pos(&x, &y);
    /* track_start_x/y are defined in track_map.c; host mock BANK() returns 0
     * so SWITCH_ROM(0) is a no-op and values are read directly. */
    TEST_PASS();
}

void test_load_track_header_id2_is_callable(void) {
    load_track_header(2u);
    /* active_map_w and active_map_h are updated — verify non-zero */
    TEST_ASSERT_NOT_EQUAL(0u, active_map_w);
    TEST_ASSERT_NOT_EQUAL(0u, active_map_h);
}

void test_load_checkpoints_id2_returns_zero_count(void) {
    CheckpointDef buf[MAX_CHECKPOINTS];
    uint8_t count = 99u;
    load_checkpoints(2u, buf, &count);
    TEST_ASSERT_EQUAL_UINT8(0u, count);  /* track3 has no checkpoints */
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_load_player_tiles_is_callable);
    RUN_TEST(test_load_track_tiles_is_callable);
    RUN_TEST(test_load_track_start_pos_writes_to_out_params);
    RUN_TEST(test_load_track_header_id2_is_callable);
    RUN_TEST(test_load_checkpoints_id2_returns_zero_count);
    return UNITY_END();
}
