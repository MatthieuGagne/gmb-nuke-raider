#include "unity.h"
#include <gb/gb.h>
#include "player.h"
#include "camera.h"

void setUp(void) {
    mock_vram_clear();
    camera_init(88, 720);  /* cam_y = 648 */
    player_init();
}
void tearDown(void) {}

/* --- start position ---------------------------------------------------- */

void test_player_init_sets_start_position(void) {
    TEST_ASSERT_EQUAL_INT16(88, player_get_x());
    TEST_ASSERT_EQUAL_INT16(720, player_get_y());
}

/* --- basic movement from track spawn (88,720) on road (cols 6-17, row 90) */

void test_player_update_moves_left(void) {
    player_update(J_LEFT);
    TEST_ASSERT_EQUAL_INT16(87, player_get_x());
}

void test_player_update_moves_right(void) {
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_INT16(89, player_get_x());
}

void test_player_update_moves_up(void) {
    player_update(J_UP);
    TEST_ASSERT_EQUAL_INT16(719, player_get_y());
}

void test_player_update_moves_down(void) {
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_INT16(721, player_get_y());
}

/* --- track collision (new map geometry) -------------------------------- */

/* Left wall: tile col 3 (x=24-31) is off-track for rows 0-49 */
void test_player_blocked_by_left_wall(void) {
    player_set_pos(32, 80);   /* leftmost road tile (col 4, x=32) */
    player_update(J_LEFT);    /* new_px=31 -> col 3 -> off-track -> blocked */
    TEST_ASSERT_EQUAL_INT16(32, player_get_x());
}

/* Right wall: corner px+7=128 -> tile col 16 -> off-track */
void test_player_blocked_by_right_wall(void) {
    player_set_pos(120, 80);  /* rightmost safe: corner at 127 (col 15, road) */
    player_update(J_RIGHT);   /* new_px=121 -> corner at 128 (col 16) -> off-track */
    TEST_ASSERT_EQUAL_INT16(120, player_get_x());
}

/* --- screen X clamp [0, 159] ------------------------------------------- */

void test_player_clamped_at_screen_left(void) {
    player_set_pos(0, 80);
    player_update(J_LEFT);    /* new_px=-1 < 0 -> blocked */
    TEST_ASSERT_EQUAL_INT16(0, player_get_x());
}

void test_player_clamped_at_screen_right(void) {
    player_set_pos(159, 80);
    player_update(J_RIGHT);   /* new_px=160 > 159 -> blocked */
    TEST_ASSERT_EQUAL_INT16(159, player_get_x());
}

/* --- screen Y clamp [cam_y, cam_y+143] ---------------------------------- */

/* cam_y=648. Player at py=648 (top of screen). Track at (80,647) IS passable
 * (col 10, row 80 = road), so ONLY screen clamp prevents upward movement. */
void test_player_clamped_at_screen_top(void) {
    player_set_pos(80, 648);  /* py == cam_y: at top of viewport */
    player_update(J_UP);      /* new_py=647 < cam_y=648 -> blocked */
    TEST_ASSERT_EQUAL_INT16(648, player_get_y());
}

/* cam_y=648, cam_y+143=791. Track at (80,792) IS passable (col 10, row 99 = road),
 * so ONLY screen clamp prevents downward movement past screen bottom. */
void test_player_clamped_at_screen_bottom(void) {
    player_set_pos(80, 791);  /* py == cam_y+143: at bottom of viewport */
    player_update(J_DOWN);    /* new_py=792 > cam_y+143=791 -> blocked */
    TEST_ASSERT_EQUAL_INT16(791, player_get_y());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_player_init_sets_start_position);
    RUN_TEST(test_player_update_moves_left);
    RUN_TEST(test_player_update_moves_right);
    RUN_TEST(test_player_update_moves_up);
    RUN_TEST(test_player_update_moves_down);
    RUN_TEST(test_player_blocked_by_left_wall);
    RUN_TEST(test_player_blocked_by_right_wall);
    RUN_TEST(test_player_clamped_at_screen_left);
    RUN_TEST(test_player_clamped_at_screen_right);
    RUN_TEST(test_player_clamped_at_screen_top);
    RUN_TEST(test_player_clamped_at_screen_bottom);
    return UNITY_END();
}
