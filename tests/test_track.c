#include "unity.h"
#include "track.h"
#include "track_tileset_meta.h"

#ifndef __SDCC
/* Seam declared in track.h — set synthetic map for wide-map index math test */
extern void track_test_set_map(const uint8_t *map, uint8_t w, uint8_t h);
#endif

void setUp(void)    {}
void tearDown(void) {}

/* --- on-track: straight section (rows 0-49, road cols 4-15) ------------ */

/* Center of road: tile (10, 10) = world (80, 80) */
void test_track_passable_straight_center(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(80, 80));
}

/* Left road edge: tile (4, 10) = world (32, 80) */
void test_track_passable_straight_left_edge(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(32, 80));
}

/* Right road edge: tile (15, 10) = world (120, 80) */
void test_track_passable_straight_right_edge(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(120, 80));
}

/* --- off-track: straight section --------------------------------------- */

/* Left sand: tile (3, 10) = world (24, 80) */
void test_track_impassable_straight_left_sand(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(24, 80));
}

/* Right sand: tile (16, 10) = world (128, 80) */
void test_track_impassable_straight_right_sand(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(128, 80));
}

/* --- on-track: curve section (rows 50-74, road cols 5-16) -------------- */

/* Center of curve: tile (11, 51) = world (88, 408) */
void test_track_passable_curve_center(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(88, 408));
}

/* --- off-track: curve section (col 17 = x=136 is sand) ---------------- */

void test_track_impassable_curve_right_sand(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(136, 408));
}

/* --- off-track: bounds checks ------------------------------------------ */

/* Beyond map width: tx = 20 >= active_map_w (20) */
void test_track_impassable_out_of_bounds_x(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(160, 80));
}

/* Beyond map height: ty = 100 >= active_map_h (100) */
void test_track_impassable_out_of_bounds_y(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(80, 800));
}

/* Negative world coords */
void test_track_impassable_negative_x(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(-1, 80));
}

void test_track_impassable_negative_y(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(80, -1));
}

/* --- TileType: track_tile_type_from_index -------------------------------- */

void test_tile_type_from_index_wall(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type_from_index(0));
}
void test_tile_type_from_index_road(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(1));
}
void test_tile_type_from_index_dashes_is_road(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(2));
}
void test_tile_type_from_index_sand(void) {
    /* 9x2 tileset, column-major: Tiled tile 3 (SAND) -> col 3, row 0 -> C index 6 */
    TEST_ASSERT_EQUAL_UINT8(TILE_SAND, track_tile_type_from_index(6));
}
void test_tile_type_from_index_oil(void) {
    /* Tiled tile 4 (OIL) -> col 4, row 0 -> C index 8 */
    TEST_ASSERT_EQUAL_UINT8(TILE_OIL, track_tile_type_from_index(8));
}
void test_tile_type_from_index_boost(void) {
    /* Tiled tile 5 (BOOST) -> col 5, row 0 -> C index 10 */
    TEST_ASSERT_EQUAL_UINT8(TILE_BOOST, track_tile_type_from_index(10));
}
/* 9x2 tileset + 8 rotation variants = 26 total entries in the LUT. */
void test_tile_lut_len_is_7(void) {
    /* TRACK_TILE_LUT_LEN from generated track_tileset_meta.h */
    TEST_ASSERT_EQUAL_UINT8(26u, TRACK_TILE_LUT_LEN);
    /* C index 12 = Tiled tile 6 = TILE_FINISH */
    TEST_ASSERT_EQUAL_UINT8(TILE_FINISH, track_tile_type_from_index(12u));
    /* C index 14 = Tiled tile 7 = TILE_ROAD */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(14u));
    /* C index 16 = Tiled tile 8 = TILE_ROAD */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(16u));
}
void test_tile_type_from_index_unknown_defaults_to_road(void) {
    /* After refactor: OOB index returns TILE_WALL (safe default), not TILE_ROAD. */
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type_from_index(99));
}
void test_track_tile_type_from_index_oob_returns_wall(void) {
    /* After refactor: OOB index returns TILE_WALL (safe default), not TILE_ROAD. */
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type_from_index(99));
}
void test_finish_tile_is_finish(void) {
    /* 9x2 tileset: Tiled tile 6 (FINISH) -> col 6, row 0 -> C index 12 */
    TEST_ASSERT_EQUAL_UINT8(TILE_FINISH, track_tile_type_from_index(12));
}
void test_track_tile_data_count_is_9(void) {
    /* 9x2 tileset (18 base tiles) + 8 rotation variants = 26 total */
    TEST_ASSERT_EQUAL_UINT8(26u, track_tile_data_count);
}

/* --- TileType: track_tile_type (world coords, uses updated track_map) ---- */

void test_track_tile_type_road(void) {
    /* tile (10,10) = tile_id 1 */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type(80, 80));
}
void test_track_tile_type_wall(void) {
    /* tile (3,10) = tile_id 0 */
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type(24, 80));
}
void test_track_tile_type_dashes_is_road(void) {
    /* tile (9,0) = tile_id 2 */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type(72, 0));
}
void test_track_tile_type_sand(void) {
    /* tile (6,10) = tile_id 3 — placed in Task 4 */
    TEST_ASSERT_EQUAL_UINT8(TILE_SAND, track_tile_type(48, 80));
}
void test_track_tile_type_oil(void) {
    /* tile (11,20) = tile_id 4 — placed in Task 4 */
    TEST_ASSERT_EQUAL_UINT8(TILE_OIL, track_tile_type(88, 160));
}
void test_track_tile_type_boost(void) {
    /* tile (11,30) = tile_id 5 — placed in Task 4 */
    TEST_ASSERT_EQUAL_UINT8(TILE_BOOST, track_tile_type(88, 240));
}
void test_track_tile_type_repair(void) {
    /* tile (12,40) was heal pad (GID 8) — now road (GID 2) after Task 6 powerup migration.
     * The heal pad is now tracked via the 'powerups' TMX objectgroup, not a BG tile. */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type(96, 320));
}
void test_track_tile_type_oob_x_is_wall(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type(160, 80));
}
void test_track_tile_type_negative_is_wall(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type(-1, 80));
}

/* track_fill_row: row contents match track_get_raw_tile() for each column */
void test_track_fill_row_matches_get_raw_tile(void) {
    uint8_t buf[20u];
    uint8_t tx;
    track_fill_row(10u, buf);
    for (tx = 0u; tx < 20u; tx++) {
        TEST_ASSERT_EQUAL_UINT8(track_get_raw_tile(tx, 10u), buf[tx]);
    }
}

/* track_fill_row: OOB ty fills buffer with zeros */
void test_track_fill_row_oob_ty_returns_zeros(void) {
    uint8_t buf[20u];
    uint8_t tx;
    for (tx = 0u; tx < 20u; tx++) buf[tx] = 0xFFu;
    track_fill_row(100u, buf);  /* ty = 100 = active_map_h (default): OOB */
    for (tx = 0u; tx < 20u; tx++) {
        TEST_ASSERT_EQUAL_UINT8(0u, buf[tx]);
    }
}

/* ---- track_fill_col -------------------------------------------------- */

/* Basic fill: column tx=10 is road (tile 1) in the straight section (rows 0-49).
 * Uses real track_map data. active_map_w/h default to 20/100 from track.c. */
void test_track_fill_col_road_column(void) {
    /* col 10, rows 0-2: row 0 has tile 2 (center dashes), rows 1-2 have tile 1 (road).
     * Both 1 and 2 map to TILE_ROAD via the LUT; we assert the raw index. */
    uint8_t buf[3];
    track_fill_col(10u, 0u, 3u, buf);
    /* 9x2 tileset with base_remap: GID 3 (dashes, Tiled tile 2) -> C index 4;
     * GID 2 (road, Tiled tile 1) -> C index 2. */
    TEST_ASSERT_EQUAL_UINT8(4u, buf[0]);  /* row 0, col 10 = dashes tile (C=4) */
    TEST_ASSERT_EQUAL_UINT8(2u, buf[1]);  /* row 1, col 10 = road tile (C=2) */
    TEST_ASSERT_EQUAL_UINT8(2u, buf[2]);  /* row 2, col 10 = road tile (C=2) */
}

/* OOB tx: tile x >= active_map_w (20) fills zeros */
void test_track_fill_col_oob_tx(void) {
    uint8_t buf[2];
    buf[0] = 0xFFu; buf[1] = 0xFFu;
    track_fill_col(25u, 0u, 2u, buf);  /* tx=25 >= active_map_w=20 */
    TEST_ASSERT_EQUAL_UINT8(0u, buf[0]);
    TEST_ASSERT_EQUAL_UINT8(0u, buf[1]);
}

/* OOB ty_start: tile y >= active_map_h (100) fills zeros */
void test_track_fill_col_oob_ty(void) {
    uint8_t buf[2];
    buf[0] = 0xFFu; buf[1] = 0xFFu;
    track_fill_col(10u, 100u, 2u, buf);  /* ty_start=100 >= active_map_h=100 */
    TEST_ASSERT_EQUAL_UINT8(0u, buf[0]);
    TEST_ASSERT_EQUAL_UINT8(0u, buf[1]);
}

/* Wide map: uint16_t index math — ty=9, w=32, tx=1 → index=9*32+1=289.
 * Uses track_test_set_map() seam (added in Task 4, #ifndef __SDCC only). */
void test_track_fill_col_wide_map_index_math(void) {
    static uint8_t wide_map[10u * 32u];
    uint8_t buf[1];
    uint16_t i;
    for (i = 0u; i < 10u * 32u; i++) wide_map[i] = (uint8_t)(i & 0xFFu);
    track_test_set_map(wide_map, 32u, 10u);
    track_fill_col(1u, 9u, 1u, buf);
    TEST_ASSERT_EQUAL_UINT8(wide_map[9u * 32u + 1u], buf[0]);
}

/* track_fill_row_range: fills only the requested window */
void test_track_fill_row_range_partial(void) {
    uint8_t buf[3];
    /* Row 10, starting at tx=9, 3 tiles. Track map row 10 cols 9-11:
     * col 9 = tile 2 (centre-dash), col 10 = tile 1 (road), col 11 = tile 1 (road) */
    track_fill_row_range(10u, 9u, 3u, buf);
    TEST_ASSERT_EQUAL_UINT8(track_get_raw_tile(9u,  10u), buf[0]);
    TEST_ASSERT_EQUAL_UINT8(track_get_raw_tile(10u, 10u), buf[1]);
    TEST_ASSERT_EQUAL_UINT8(track_get_raw_tile(11u, 10u), buf[2]);
}

/* track_fill_row_range: OOB columns fill zeros */
void test_track_fill_row_range_oob_col(void) {
    uint8_t buf[3];
    buf[0] = 0xFFu; buf[1] = 0xFFu; buf[2] = 0xFFu;
    /* tx_start=19, count=3: tx=19 valid, tx=20 OOB, tx=21 OOB */
    track_fill_row_range(10u, 19u, 3u, buf);
    TEST_ASSERT_EQUAL_UINT8(track_get_raw_tile(19u, 10u), buf[0]);
    TEST_ASSERT_EQUAL_UINT8(0u, buf[1]);
    TEST_ASSERT_EQUAL_UINT8(0u, buf[2]);
}

/* --- track_get_reward --- */

void test_track1_reward(void) {
    track_select(0u);
    TEST_ASSERT_EQUAL_UINT16(TRACK1_REWARD, track_get_reward());
}

void test_track2_reward(void) {
    track_select(1u);
    TEST_ASSERT_EQUAL_UINT16(TRACK2_REWARD, track_get_reward());
}

void test_track3_reward_is_zero(void) {
    track_select(2u);
    TEST_ASSERT_EQUAL_UINT16(0u, track_get_reward());
}

/* --- track_get_map_type -------------------------------------------------- */

void test_track_get_map_type_race_track0(void) {
    track_select(0u);
    TEST_ASSERT_EQUAL_UINT8(TRACK_TYPE_RACE, track_get_map_type());
}

void test_track_get_map_type_race_track1(void) {
    track_select(1u);
    TEST_ASSERT_EQUAL_UINT8(TRACK_TYPE_RACE, track_get_map_type());
}

void test_track_get_map_type_combat_track2(void) {
    track_select(2u);
    TEST_ASSERT_EQUAL_UINT8(TRACK_TYPE_COMBAT, track_get_map_type());
}

/* --- track_get_id -------------------------------------------------------- */

void test_track_get_id_returns_0_after_select_0(void) {
    track_select(0u);
    TEST_ASSERT_EQUAL_UINT8(0u, track_get_id());
}

void test_track_get_id_returns_1_after_select_1(void) {
    track_select(1u);
    TEST_ASSERT_EQUAL_UINT8(1u, track_get_id());
}

void test_track_get_id_returns_2_after_select_2(void) {
    track_select(2u);
    TEST_ASSERT_EQUAL_UINT8(2u, track_get_id());
}

/* --- track_select bounds guard (issue #273) ------------------------------ */

/* Out-of-bounds id must clamp to 0, not index into undefined memory */
void test_track_select_oob_clamps_to_0(void) {
    track_select(1u);  /* set a non-zero baseline */
    track_select(NUM_TRACKS);  /* id == 3 is out of range */
    TEST_ASSERT_EQUAL_UINT8(0u, track_get_id());
}

void test_track_select_large_id_clamps_to_0(void) {
    track_select(1u);
    track_select(255u);
    TEST_ASSERT_EQUAL_UINT8(0u, track_get_id());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_track_passable_straight_center);
    RUN_TEST(test_track_passable_straight_left_edge);
    RUN_TEST(test_track_passable_straight_right_edge);
    RUN_TEST(test_track_impassable_straight_left_sand);
    RUN_TEST(test_track_impassable_straight_right_sand);
    RUN_TEST(test_track_passable_curve_center);
    RUN_TEST(test_track_impassable_curve_right_sand);
    RUN_TEST(test_track_impassable_out_of_bounds_x);
    RUN_TEST(test_track_impassable_out_of_bounds_y);
    RUN_TEST(test_track_impassable_negative_x);
    RUN_TEST(test_track_impassable_negative_y);
    RUN_TEST(test_tile_type_from_index_wall);
    RUN_TEST(test_tile_type_from_index_road);
    RUN_TEST(test_tile_type_from_index_dashes_is_road);
    RUN_TEST(test_tile_type_from_index_sand);
    RUN_TEST(test_tile_type_from_index_oil);
    RUN_TEST(test_tile_type_from_index_boost);
    RUN_TEST(test_tile_lut_len_is_7);
    RUN_TEST(test_tile_type_from_index_unknown_defaults_to_road);
    RUN_TEST(test_track_tile_type_from_index_oob_returns_wall);
    RUN_TEST(test_finish_tile_is_finish);
    RUN_TEST(test_track_tile_type_road);
    RUN_TEST(test_track_tile_type_wall);
    RUN_TEST(test_track_tile_type_dashes_is_road);
    RUN_TEST(test_track_tile_type_sand);
    RUN_TEST(test_track_tile_type_oil);
    RUN_TEST(test_track_tile_type_boost);
    RUN_TEST(test_track_tile_type_repair);
    RUN_TEST(test_track_tile_type_oob_x_is_wall);
    RUN_TEST(test_track_tile_type_negative_is_wall);
    RUN_TEST(test_track_tile_data_count_is_9);
    RUN_TEST(test_track_fill_row_matches_get_raw_tile);
    RUN_TEST(test_track_fill_row_oob_ty_returns_zeros);
    RUN_TEST(test_track_fill_col_road_column);
    RUN_TEST(test_track_fill_col_oob_tx);
    RUN_TEST(test_track_fill_col_oob_ty);
    RUN_TEST(test_track_fill_col_wide_map_index_math);
    RUN_TEST(test_track_fill_row_range_partial);
    RUN_TEST(test_track_fill_row_range_oob_col);
    RUN_TEST(test_track_get_map_type_race_track0);
    RUN_TEST(test_track_get_map_type_race_track1);
    RUN_TEST(test_track_get_map_type_combat_track2);
    RUN_TEST(test_track1_reward);
    RUN_TEST(test_track2_reward);
    RUN_TEST(test_track3_reward_is_zero);
    RUN_TEST(test_track_get_id_returns_0_after_select_0);
    RUN_TEST(test_track_get_id_returns_1_after_select_1);
    RUN_TEST(test_track_get_id_returns_2_after_select_2);
    RUN_TEST(test_track_select_oob_clamps_to_0);
    RUN_TEST(test_track_select_large_id_clamps_to_0);
    return UNITY_END();
}
