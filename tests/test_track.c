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
    return UNITY_END();
}
