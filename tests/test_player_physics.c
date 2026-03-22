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
    input = J_RIGHT | J_UP;
    player_update();
    TEST_ASSERT_EQUAL_INT8(0,              player_get_vx()); /* wall blocks x */
    TEST_ASSERT_EQUAL_INT8(-PLAYER_ACCEL,  player_get_vy()); /* UP still moves forward */
}

/* --- AC5: wall collision zeros vy, not vx ------------------------------- */

/* Player at py=cam_y (648): screen top acts as wall.
 * Moving up (gas): new_py < cam_y → blocked → vy=0. */
void test_wall_zeros_vy_not_vx(void) {
    player_set_pos(88, 648);  /* py == cam_y: at screen top */
    input = J_UP | J_A;
    player_update();
    TEST_ASSERT_EQUAL_INT8(0, player_get_vy());
    TEST_ASSERT_EQUAL_INT8(0, player_get_vx());
}

/* --- AC6: X and Y axes accumulate independently to max speed ----------- */

/* D-pad L/R and A operate on separate axes with no friction while held.
 * Holding J_RIGHT | J_A accumulates both vx and vy to PLAYER_MAX_SPEED. */
void test_x_and_y_axes_accumulate_independently(void) {
    uint8_t i;
    input = J_RIGHT | J_UP;
    for (i = 0; i < PLAYER_MAX_SPEED / PLAYER_ACCEL; i++) {
        player_update();
    }
    TEST_ASSERT_EQUAL_INT8( PLAYER_MAX_SPEED, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(-PLAYER_MAX_SPEED, player_get_vy());
}

/* Player cannot move into the HUD band (bottom 16px reserved for Window layer).
 * cam_y=0, player at screen Y 112 (world py=112): bottom of 16px car = pixel 127.
 * Moving down one more pixel (py=113, screen Y 113, bottom=128) must be blocked. */
void test_y_clamped_above_hud(void) {
    camera_init(88, 0);       /* cam_y = 0 */
    player_set_pos(88, 112);  /* screen Y = 112, car bottom = 127 — just inside play area */
    input = J_DOWN;
    player_update();           /* reverse from stopped pushes py to 113 > HUD boundary (112) — blocked */
    TEST_ASSERT_TRUE(player_get_y() <= 112);  /* must not cross into HUD */
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_accel_reaches_max_speed);
    RUN_TEST(test_accel_capped_at_max_speed);
    RUN_TEST(test_friction_decelerates_to_zero);
    RUN_TEST(test_wall_zeros_vx_not_vy);
    RUN_TEST(test_wall_zeros_vy_not_vx);
    RUN_TEST(test_x_and_y_axes_accumulate_independently);
    RUN_TEST(test_y_clamped_above_hud);
    return UNITY_END();
}
