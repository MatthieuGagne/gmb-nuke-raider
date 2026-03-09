#include "unity.h"
#include "track.h"

void setUp(void)    {}
void tearDown(void) {}

/* On-track: bottom straight, row 14 col 10 — screen (80, 112) */
void test_track_passable_bottom_straight(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(80, 112));
}

/* On-track: left side, row 7 col 2 — screen (16, 56) */
void test_track_passable_left_side(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(16, 56));
}

/* On-track: top straight, row 1 col 10 — screen (80, 8) */
void test_track_passable_top_straight(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(80, 8));
}

/* Off-track: outer corner, row 0 col 0 — screen (0, 0) */
void test_track_passable_outer_corner(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(0, 0));
}

/* Off-track: inner void, row 7 col 9 — screen (72, 56) */
void test_track_passable_inner_void(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(72, 56));
}

/* Off-track: below bottom of oval, row 15 col 10 — screen (80, 120) */
void test_track_passable_below_oval(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(80, 120));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_track_passable_bottom_straight);
    RUN_TEST(test_track_passable_left_side);
    RUN_TEST(test_track_passable_top_straight);
    RUN_TEST(test_track_passable_outer_corner);
    RUN_TEST(test_track_passable_inner_void);
    RUN_TEST(test_track_passable_below_oval);
    return UNITY_END();
}
