#include "unity.h"
#include "player.h"

void setUp(void)    { player_init(); }
void tearDown(void) {}

/* clamp_u8 ---------------------------------------------------------- */

void test_clamp_u8_returns_lo_when_below(void) {
    TEST_ASSERT_EQUAL_UINT8(8, clamp_u8(5, 8, 152));
}

void test_clamp_u8_returns_hi_when_above(void) {
    TEST_ASSERT_EQUAL_UINT8(152, clamp_u8(200, 8, 152));
}

void test_clamp_u8_returns_value_when_within(void) {
    TEST_ASSERT_EQUAL_UINT8(80, clamp_u8(80, 8, 152));
}

/* player_init ------------------------------------------------------- */

/* New start: hw (88, 124) = screen (80, 108) = tile (10, 13) — center of bottom straight */
void test_player_init_sets_center_position(void) {
    TEST_ASSERT_EQUAL_UINT8(88, player_get_x());
    TEST_ASSERT_EQUAL_UINT8(124, player_get_y());
}

/* player_update movement -------------------------------------------- */

void test_player_update_moves_left(void) {
    player_update(J_LEFT);
    TEST_ASSERT_EQUAL_UINT8(87, player_get_x());
}

void test_player_update_moves_right(void) {
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(89, player_get_x());
}

void test_player_update_moves_up(void) {
    player_update(J_UP);
    TEST_ASSERT_EQUAL_UINT8(123, player_get_y());
}

void test_player_update_moves_down(void) {
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(125, player_get_y());
}

/* player_update clamping -------------------------------------------- */

void test_player_update_clamps_at_left_boundary(void) {
    player_set_pos(8, 72);
    player_update(J_LEFT);
    TEST_ASSERT_EQUAL_UINT8(8, player_get_x());
}

void test_player_update_clamps_at_right_boundary(void) {
    player_set_pos(160, 72);
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(160, player_get_x());
}

void test_player_update_clamps_at_top_boundary(void) {
    player_set_pos(80, 16);
    player_update(J_UP);
    TEST_ASSERT_EQUAL_UINT8(16, player_get_y());
}

void test_player_update_clamps_at_bottom_boundary(void) {
    player_set_pos(80, 152);
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(152, player_get_y());
}

/* player_update track collision ------------------------------------- */

/* Collision: player blocked at left track boundary
 * hw (32, 120) = screen (24, 104) = tile (3, 13) — on track (row 13 col 3 = 1)
 * moving left: screen x=23, tile col 2 = 0 (off-track) → blocked */
void test_player_blocked_by_track_left(void) {
    player_set_pos(32, 120);
    player_update(J_LEFT);
    TEST_ASSERT_EQUAL_UINT8(32, player_get_x());
}

/* Collision: player blocked at bottom track boundary
 * hw (88, 128) = screen (80, 112) = tile (10, 14) — on track (row 14 col 10 = 1)
 * moving down: bottom corner at screen y=120, tile row 15 = 0 → blocked */
void test_player_blocked_by_track_bottom(void) {
    player_set_pos(88, 128);
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(128, player_get_y());
}

/* Collision: player blocked moving up into off-track top
 * hw (88, 24) = screen (80, 8) = tile (10, 1) — on track (row 1 col 10 = 1)
 * moving up: screen y=7, tile row 0 = 0 → blocked */
void test_player_blocked_by_track_top(void) {
    player_set_pos(88, 24);
    player_update(J_UP);
    TEST_ASSERT_EQUAL_UINT8(24, player_get_y());
}

/* Sliding: player blocked moving up (off-track), but can still move right (on track)
 * Same start position as above */
void test_player_slides_right_when_up_blocked(void) {
    player_set_pos(88, 24);
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(89, player_get_x());
}

/* runner ------------------------------------------------------------ */

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_clamp_u8_returns_lo_when_below);
    RUN_TEST(test_clamp_u8_returns_hi_when_above);
    RUN_TEST(test_clamp_u8_returns_value_when_within);
    RUN_TEST(test_player_init_sets_center_position);
    RUN_TEST(test_player_update_moves_left);
    RUN_TEST(test_player_update_moves_right);
    RUN_TEST(test_player_update_moves_up);
    RUN_TEST(test_player_update_moves_down);
    RUN_TEST(test_player_update_clamps_at_left_boundary);
    RUN_TEST(test_player_update_clamps_at_right_boundary);
    RUN_TEST(test_player_update_clamps_at_top_boundary);
    RUN_TEST(test_player_update_clamps_at_bottom_boundary);
    RUN_TEST(test_player_blocked_by_track_left);
    RUN_TEST(test_player_blocked_by_track_bottom);
    RUN_TEST(test_player_blocked_by_track_top);
    RUN_TEST(test_player_slides_right_when_up_blocked);
    return UNITY_END();
}
