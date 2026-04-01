#include "unity.h"
#include "track.h"

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

/* Beyond map width: tx = 20 >= MAP_TILES_W */
void test_track_impassable_out_of_bounds_x(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(160, 80));
}

/* Beyond map height: ty = 100 >= MAP_TILES_H */
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
    TEST_ASSERT_EQUAL_UINT8(TILE_SAND, track_tile_type_from_index(3));
}
void test_tile_type_from_index_oil(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_OIL, track_tile_type_from_index(4));
}
void test_tile_type_from_index_boost(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_BOOST, track_tile_type_from_index(5));
}
void test_tile_type_from_index_repair(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_REPAIR, track_tile_type_from_index(7));
}
void test_tile_type_from_index_unknown_defaults_to_road(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(99));
}
void test_finish_tile_is_finish(void) {
    /* tile index 6 must now be TILE_FINISH (passable, triggers lap detection) */
    TEST_ASSERT_EQUAL_UINT8(TILE_FINISH, track_tile_type_from_index(6));
}
void test_track_tile_data_count_is_9(void) {
    /* tileset has 9 tiles: wall, road, center-dash, sand, oil, boost, finish, repair, turret */
    TEST_ASSERT_EQUAL_UINT8(9u, track_tile_data_count);
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
    /* tile (12,40) = tile_id 7 — repair pad placed in Task 4 */
    TEST_ASSERT_EQUAL_UINT8(TILE_REPAIR, track_tile_type(96, 320));
}
void test_track_tile_type_oob_x_is_wall(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type(160, 80));
}
void test_track_tile_type_negative_is_wall(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type(-1, 80));
}

/* track_fill_row: row contents match track_get_raw_tile() for each column */
void test_track_fill_row_matches_get_raw_tile(void) {
    uint8_t buf[MAP_TILES_W];
    uint8_t tx;
    track_fill_row(10u, buf);
    for (tx = 0u; tx < MAP_TILES_W; tx++) {
        TEST_ASSERT_EQUAL_UINT8(track_get_raw_tile(tx, 10u), buf[tx]);
    }
}

/* track_fill_row: OOB ty fills buffer with zeros */
void test_track_fill_row_oob_ty_returns_zeros(void) {
    uint8_t buf[MAP_TILES_W];
    uint8_t tx;
    for (tx = 0u; tx < MAP_TILES_W; tx++) buf[tx] = 0xFFu;
    track_fill_row(MAP_TILES_H, buf);  /* ty = 100 = MAP_TILES_H: OOB */
    for (tx = 0u; tx < MAP_TILES_W; tx++) {
        TEST_ASSERT_EQUAL_UINT8(0u, buf[tx]);
    }
}

/* --- TILE_TURRET --------------------------------------------------------- */

void test_tile_turret_type(void) {
    /* Tileset index 8 must map to TILE_TURRET */
    TEST_ASSERT_EQUAL_INT(TILE_TURRET, track_tile_type_from_index(8u));
}

void test_tile_turret_not_passable(void) {
    /* TILE_TURRET must NOT be equal to TILE_ROAD, TILE_SAND, TILE_BOOST, or TILE_REPAIR */
    TEST_ASSERT_NOT_EQUAL(TILE_ROAD,   TILE_TURRET);
    TEST_ASSERT_NOT_EQUAL(TILE_SAND,   TILE_TURRET);
    TEST_ASSERT_NOT_EQUAL(TILE_BOOST,  TILE_TURRET);
    TEST_ASSERT_NOT_EQUAL(TILE_REPAIR, TILE_TURRET);
}

/* ---- track_fill_col -------------------------------------------------- */

/* Basic fill: column tx=10 is road (tile 1) in the straight section (rows 0-49).
 * Uses real track_map data. active_map_w/h default to 20/100 from track.c. */
void test_track_fill_col_road_column(void) {
    /* col 10, rows 0-2: row 0 has tile 2 (center dashes), rows 1-2 have tile 1 (road).
     * Both 1 and 2 map to TILE_ROAD via the LUT; we assert the raw index. */
    uint8_t buf[3];
    track_fill_col(10u, 0u, 3u, buf);
    TEST_ASSERT_EQUAL_UINT8(2u, buf[0]);  /* row 0, col 10 = dashes tile */
    TEST_ASSERT_EQUAL_UINT8(1u, buf[1]);  /* row 1, col 10 = road tile */
    TEST_ASSERT_EQUAL_UINT8(1u, buf[2]);  /* row 2, col 10 = road tile */
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
    RUN_TEST(test_tile_type_from_index_repair);
    RUN_TEST(test_tile_type_from_index_unknown_defaults_to_road);
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
    RUN_TEST(test_tile_turret_type);
    RUN_TEST(test_tile_turret_not_passable);
    RUN_TEST(test_track_fill_col_road_column);
    RUN_TEST(test_track_fill_col_oob_tx);
    RUN_TEST(test_track_fill_col_oob_ty);
    RUN_TEST(test_track_fill_col_wide_map_index_math);
    RUN_TEST(test_track_fill_row_range_partial);
    RUN_TEST(test_track_fill_row_range_oob_col);
    return UNITY_END();
}
