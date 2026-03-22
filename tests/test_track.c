#include "unity.h"
#include "track.h"

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
void test_finish_tile_is_road(void) {
    /* tile index 6 (finish visual) must be classified as road — passable */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(6));
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
    RUN_TEST(test_finish_tile_is_road);
    RUN_TEST(test_track_tile_type_road);
    RUN_TEST(test_track_tile_type_wall);
    RUN_TEST(test_track_tile_type_dashes_is_road);
    RUN_TEST(test_track_tile_type_sand);
    RUN_TEST(test_track_tile_type_oil);
    RUN_TEST(test_track_tile_type_boost);
    RUN_TEST(test_track_tile_type_repair);
    RUN_TEST(test_track_tile_type_oob_x_is_wall);
    RUN_TEST(test_track_tile_type_negative_is_wall);
    return UNITY_END();
}
