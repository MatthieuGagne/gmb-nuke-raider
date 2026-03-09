#include "unity.h"
#include "player.h"

void setUp(void)    { player_init(); }
void tearDown(void) {}

/* player_init -------------------------------------------------------- */

/* Start position: world (160, 256) = tile (20,32), bottom straight center */
void test_player_init_sets_start_position(void) {
    TEST_ASSERT_EQUAL_INT16(160, player_get_x());
    TEST_ASSERT_EQUAL_INT16(256, player_get_y());
}

/* player_update movement --------------------------------------------- */

void test_player_update_moves_left(void) {
    player_update(J_LEFT);
    TEST_ASSERT_EQUAL_INT16(159, player_get_x());
}

void test_player_update_moves_right(void) {
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_INT16(161, player_get_x());
}

void test_player_update_moves_up(void) {
    player_update(J_UP);
    TEST_ASSERT_EQUAL_INT16(255, player_get_y());
}

void test_player_update_moves_down(void) {
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_INT16(257, player_get_y());
}

/* player_update track collision -------------------------------------- */

/* Left outer wall: tile col 3 (D-row) is off-track */
void test_player_blocked_by_track_left(void) {
    player_set_pos(32, 120);
    player_update(J_LEFT);
    TEST_ASSERT_EQUAL_INT16(32, player_get_x());
}

/* Right outer wall: tile col 36 (D-row) is off-track */
void test_player_blocked_by_track_right(void) {
    player_set_pos(280, 120);
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_INT16(280, player_get_x());
}

/* Top outer wall: tile row 1 (A-row) is off-track */
void test_player_blocked_by_track_top(void) {
    player_set_pos(160, 16);
    player_update(J_UP);
    TEST_ASSERT_EQUAL_INT16(16, player_get_y());
}

/* Bottom outer wall: tile row 34 (A-row) is off-track */
void test_player_blocked_by_track_bottom(void) {
    player_set_pos(160, 264);
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_INT16(264, player_get_y());
}

/* corner connectivity ------------------------------------------------ */

/* Outer-left D-row (col 4, x=32) must connect to top strip.
 * Old C-row stopped at col 6; rectangular fix extends strip to col 4. */
void test_player_outer_left_connects_to_top_strip(void) {
    player_set_pos(32, 48); /* outer-left D-row 6, col 4 */
    player_update(J_UP);    /* enter what was C-row 5 */
    TEST_ASSERT_EQUAL_INT16(47, player_get_y());
}

/* Outer-right D-row (col 35, x=280+7=287) must connect to bottom strip.
 * Old C-row stopped at col 33; rectangular fix extends strip to col 35. */
void test_player_outer_right_connects_to_bottom_strip(void) {
    player_set_pos(272, 232); /* outer-right D-row 29, col 34 */
    player_update(J_DOWN);    /* enter what was C-row 30 */
    TEST_ASSERT_EQUAL_INT16(233, player_get_y());
}

/* runner ------------------------------------------------------------- */

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_player_init_sets_start_position);
    RUN_TEST(test_player_update_moves_left);
    RUN_TEST(test_player_update_moves_right);
    RUN_TEST(test_player_update_moves_up);
    RUN_TEST(test_player_update_moves_down);
    RUN_TEST(test_player_blocked_by_track_left);
    RUN_TEST(test_player_blocked_by_track_right);
    RUN_TEST(test_player_blocked_by_track_top);
    RUN_TEST(test_player_blocked_by_track_bottom);
    RUN_TEST(test_player_outer_left_connects_to_top_strip);
    RUN_TEST(test_player_outer_right_connects_to_bottom_strip);
    return UNITY_END();
}
