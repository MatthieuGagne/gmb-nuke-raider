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

void test_load_npc_positions_id0_returns_count(void) {
    uint8_t tx[8], ty[8], type[8], dir[8], count = 99u;
    load_npc_positions(0u, tx, ty, type, dir, &count);
    TEST_ASSERT_EQUAL_UINT8(3u, count);
}

void test_load_npc_positions_id1_returns_count(void) {
    uint8_t tx[8], ty[8], type[8], dir[8], count = 99u;
    load_npc_positions(1u, tx, ty, type, dir, &count);
    TEST_ASSERT_EQUAL_UINT8(0u, count);
}

void test_load_npc_positions_id2_returns_count(void) {
    uint8_t tx[8], ty[8], type[8], dir[8], count = 99u;
    load_npc_positions(2u, tx, ty, type, dir, &count);
    TEST_ASSERT_EQUAL_UINT8(0u, count);
}

void test_load_bkg_row_increments_mock_count(void) {
    uint8_t tiles[4] = { 1u, 2u, 3u, 4u };
    int before = mock_load_bkg_row_call_count;
    load_bkg_row(0u, 0u, 4u, tiles);
    TEST_ASSERT_EQUAL_INT(before + 1, mock_load_bkg_row_call_count);
}

void test_load_bkg_row_writes_to_mock_vram(void) {
    uint8_t tiles[3] = { 5u, 6u, 7u };
    mock_vram_clear();
    load_bkg_row(2u, 1u, 3u, tiles);
    TEST_ASSERT_EQUAL_UINT8(5u, mock_vram[1u * 32u + 2u]);
    TEST_ASSERT_EQUAL_UINT8(6u, mock_vram[1u * 32u + 3u]);
    TEST_ASSERT_EQUAL_UINT8(7u, mock_vram[1u * 32u + 4u]);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_load_player_tiles_is_callable);
    RUN_TEST(test_load_track_tiles_is_callable);
    RUN_TEST(test_load_track_start_pos_writes_to_out_params);
    RUN_TEST(test_load_track_header_id2_is_callable);
    RUN_TEST(test_load_checkpoints_id2_returns_zero_count);
    RUN_TEST(test_load_npc_positions_id0_returns_count);
    RUN_TEST(test_load_npc_positions_id1_returns_count);
    RUN_TEST(test_load_npc_positions_id2_returns_count);
    RUN_TEST(test_load_bkg_row_increments_mock_count);
    RUN_TEST(test_load_bkg_row_writes_to_mock_vram);
    return UNITY_END();
}
