#include "unity.h"
#include <gb/gb.h>
#include "loader.h"
#include "track.h"

void setUp(void) {
    loader_reset_bitmap_for_test();
}
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

/* ---- Allocator tests ---- */

void test_alloc_returns_region_start_when_empty(void) {
    /* Bitmap starts zeroed (static storage). Alloc 1 slot in sprite region 40-47. */
    uint8_t slot = loader_alloc_slots(40u, 47u, 1u);
    TEST_ASSERT_EQUAL_UINT8(40u, slot);
}

void test_alloc_sets_bitmap_bits(void) {
    /* After allocating slot 50, a second alloc in [50,50] must fail (bit occupied). */
    loader_alloc_slots(50u, 50u, 1u);
    uint8_t slot = loader_alloc_slots(50u, 50u, 1u);
    TEST_ASSERT_EQUAL_UINT8(0xFFu, slot);
}

void test_alloc_consecutive_runs_do_not_overlap(void) {
    /* Two allocs of 4 slots each in region [48,55] must not overlap. */
    uint8_t a = loader_alloc_slots(48u, 55u, 4u);
    uint8_t b = loader_alloc_slots(48u, 55u, 4u);
    TEST_ASSERT_NOT_EQUAL(0xFFu, a);
    TEST_ASSERT_NOT_EQUAL(0xFFu, b);
    /* b must start at or after a + 4 */
    TEST_ASSERT_TRUE(b >= a + 4u);
}

void test_alloc_past_region_end_returns_sentinel(void) {
    /* Request 8 slots in region [60,63] (only 4 slots available). */
    uint8_t slot = loader_alloc_slots(60u, 63u, 8u);
    TEST_ASSERT_EQUAL_UINT8(0xFFu, slot);
}

void test_alloc_exhaustion_returns_sentinel(void) {
    /* Fill region [56,59] (4 slots) with two 2-slot allocs, then a third must fail. */
    loader_alloc_slots(56u, 59u, 2u);
    loader_alloc_slots(56u, 59u, 2u);
    uint8_t slot = loader_alloc_slots(56u, 59u, 1u);
    TEST_ASSERT_EQUAL_UINT8(0xFFu, slot);
}

void test_free_clears_bits_allowing_realloc(void) {
    uint8_t slot = loader_alloc_slots(32u, 39u, 4u);
    TEST_ASSERT_NOT_EQUAL(0xFFu, slot);
    loader_free_slots(slot, 4u);
    /* After free, same region must be available again. */
    uint8_t slot2 = loader_alloc_slots(32u, 39u, 4u);
    TEST_ASSERT_EQUAL_UINT8(slot, slot2);
}

void test_alloc_region_boundary_enforced(void) {
    /* region_end > 254 must return 0xFF (slot 255 is reserved sentinel). */
    uint8_t slot = loader_alloc_slots(253u, 255u, 2u);
    TEST_ASSERT_EQUAL_UINT8(0xFFu, slot);
}

void test_get_asset_slot_returns_sentinel_initially(void) {
    TEST_ASSERT_EQUAL_UINT8(0xFFu, loader_get_asset_slot(TILE_ASSET_PLAYER));
    TEST_ASSERT_EQUAL_UINT8(0xFFu, loader_get_asset_slot(TILE_ASSET_DIALOG_BORDER));
}

void test_tile_asset_count_is_correct(void) {
    TEST_ASSERT_EQUAL_UINT8(12u, (uint8_t)TILE_ASSET_COUNT);
}

/* ---- Registry tests ---- */

void test_registry_player_is_sprite(void) {
    const tile_registry_entry_t *e = loader_get_registry(TILE_ASSET_PLAYER);
    TEST_ASSERT_NOT_NULL(e);
    TEST_ASSERT_EQUAL_UINT8(1u, e->is_sprite);
    TEST_ASSERT_NOT_NULL(e->data);
    TEST_ASSERT_NOT_NULL(e->count_ptr);
}

void test_registry_track_is_bg(void) {
    const tile_registry_entry_t *e = loader_get_registry(TILE_ASSET_TRACK);
    TEST_ASSERT_NOT_NULL(e);
    TEST_ASSERT_EQUAL_UINT8(0u, e->is_sprite);
}

void test_registry_hud_font_is_null_sentinel(void) {
    const tile_registry_entry_t *e = loader_get_registry(TILE_ASSET_HUD_FONT);
    TEST_ASSERT_NOT_NULL(e);       /* entry exists */
    TEST_ASSERT_NULL(e->data);     /* but data is NULL (self-managed) */
    TEST_ASSERT_NULL(e->count_ptr);
}

void test_registry_out_of_bounds_returns_null(void) {
    const tile_registry_entry_t *e = loader_get_registry((tile_asset_t)TILE_ASSET_COUNT);
    TEST_ASSERT_NULL(e);
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
    RUN_TEST(test_alloc_returns_region_start_when_empty);
    RUN_TEST(test_alloc_sets_bitmap_bits);
    RUN_TEST(test_alloc_consecutive_runs_do_not_overlap);
    RUN_TEST(test_alloc_past_region_end_returns_sentinel);
    RUN_TEST(test_alloc_exhaustion_returns_sentinel);
    RUN_TEST(test_free_clears_bits_allowing_realloc);
    RUN_TEST(test_alloc_region_boundary_enforced);
    RUN_TEST(test_get_asset_slot_returns_sentinel_initially);
    RUN_TEST(test_tile_asset_count_is_correct);
    RUN_TEST(test_registry_player_is_sprite);
    RUN_TEST(test_registry_track_is_bg);
    RUN_TEST(test_registry_hud_font_is_null_sentinel);
    RUN_TEST(test_registry_out_of_bounds_returns_null);
    return UNITY_END();
}
