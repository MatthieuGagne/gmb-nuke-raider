/* tests/test_player_physics.c — velocity, acceleration, friction, wall collision */
#include "unity.h"
#include <gb/gb.h>
#include "../src/input.h"
#include "../src/config.h"
#include "player.h"
#include "camera.h"

/* input/prev_input globals defined in tests/mocks/input_globals.c */

void setUp(void) {
    input = 0;
    prev_input = 0;
    mock_vram_clear();
    camera_init(88, 720);  /* cam_y = 648 */
    player_init();
    player_set_pos(88, 720);  /* track start: col 11, row 90 — road */
}
void tearDown(void) {}

/* --- AC1: acceleration reaches max speed -------------------------------- */

/* Holding J_RIGHT | J_A: X friction is 0 while J_RIGHT pressed, so vx accumulates
 * by PLAYER_ACCEL each frame up to PLAYER_MAX_SPEED. */
void test_accel_reaches_max_speed(void) {
    uint8_t i;
    input = J_RIGHT | J_A;
    for (i = 0; i < PLAYER_MAX_SPEED / PLAYER_ACCEL; i++) player_update();
    TEST_ASSERT_EQUAL_INT8(PLAYER_MAX_SPEED, player_get_vx());
}

/* --- AC2: velocity capped at max speed ---------------------------------- */

/* Additional frames beyond max do not exceed PLAYER_MAX_SPEED. */
void test_accel_capped_at_max_speed(void) {
    uint8_t i;
    input = J_RIGHT | J_A;
    for (i = 0; i <= PLAYER_MAX_SPEED / PLAYER_ACCEL; i++) player_update(); /* one extra */
    TEST_ASSERT_EQUAL_INT8(PLAYER_MAX_SPEED, player_get_vx());
}

/* --- AC3: friction decelerates to zero ---------------------------------- */

/* Releasing direction from vx=MAX_SPEED reaches vx==0 within
 * MAX_SPEED/FRICTION frames. */
void test_friction_decelerates_to_zero(void) {
    uint8_t i;
    input = J_RIGHT | J_A;
    for (i = 0; i < PLAYER_MAX_SPEED / PLAYER_ACCEL; i++) player_update(); /* reach max */
    input = 0;
    for (i = 0; i < PLAYER_MAX_SPEED / PLAYER_FRICTION; i++) player_update(); /* friction */
    TEST_ASSERT_EQUAL_INT8(0, player_get_vx());
}

/* --- AC4: wall collision zeros vx, not vy ------------------------------- */

/* Row 90 (y=720) road: cols 6-17 (x=48-143). Right wall at col 18 (x=144+).
 * Player at px=136: corner px+7=143 (col 17 = road).
 * Moving right (gas): new_px=137, corner=144 (col 18 = sand) → blocked → vx=0. */
void test_wall_zeros_vx_not_vy(void) {
    player_set_pos(136, 720);
    input = J_RIGHT | J_UP;  /* face NE, gas → vx blocked by wall, vy moves */
    player_update();
    TEST_ASSERT_EQUAL_INT8(0,              player_get_vx()); /* wall blocks x */
    TEST_ASSERT_EQUAL_INT8(-PLAYER_ACCEL,  player_get_vy()); /* UP still moves forward */
}

/* --- AC5: wall collision zeros vy, not vx ------------------------------- */

/* Player at py=0 (map top): moving up → new_py=-1 < 0 → map clamp blocks → vy=0. */
void test_wall_zeros_vy_not_vx(void) {
    player_set_pos(88, 0);   /* py at map top boundary */
    input = J_UP | J_A;
    player_update();
    TEST_ASSERT_EQUAL_INT8(0, player_get_vy());
    TEST_ASSERT_EQUAL_INT8(0, player_get_vx());
}

/* --- AC6: X and Y axes accumulate independently to max speed ----------- */

/* NE facing + gas: both axes accumulate to PLAYER_MAX_SPEED independently. */
void test_x_and_y_axes_accumulate_independently(void) {
    uint8_t i;
    input = J_RIGHT | J_UP;  /* face NE, gas → vx+1 and vy-1 per frame */
    for (i = 0; i < PLAYER_MAX_SPEED / PLAYER_ACCEL; i++) {
        player_update();
    }
    TEST_ASSERT_EQUAL_INT8( PLAYER_MAX_SPEED, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(-PLAYER_MAX_SPEED, player_get_vy());
}

/* Player cannot move past map bottom boundary (MAP_PX_H-8 = 792).
 * Player at py=792: moving down → new_py=793 > 792 → map clamp blocks. */
void test_y_clamped_at_map_bottom(void) {
    player_set_pos(88, 792);  /* py at map bottom boundary */
    input = J_DOWN;
    player_update();           /* new_py=793 > MAP_PX_H-8=792 → blocked */
    TEST_ASSERT_TRUE(player_get_y() <= 792);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_accel_reaches_max_speed);
    RUN_TEST(test_accel_capped_at_max_speed);
    RUN_TEST(test_friction_decelerates_to_zero);
    RUN_TEST(test_wall_zeros_vx_not_vy);
    RUN_TEST(test_wall_zeros_vy_not_vx);
    RUN_TEST(test_x_and_y_axes_accumulate_independently);
    RUN_TEST(test_y_clamped_at_map_bottom);
    return UNITY_END();
}
