/* tests/test_player_physics.c — velocity, acceleration, friction, wall collision */
#include "unity.h"
#include <gb/gb.h>
#include "../src/input.h"
#include "../src/config.h"
#include "player.h"
#include "camera.h"
#include "track.h"

/* The turn period comes from config.h, not from a number typed here, so these tests
 * stay correct when PLAYER_HANDLING or the table is retuned (#628). */
static const uint8_t TURN_FRAMES_T[8] = PLAYER_TURN_FRAMES_TABLE;
#define TURN_PERIOD  (TURN_FRAMES_T[PLAYER_HANDLING])

/* D-pad buttons that decode to each of the eight player facings. */
static const uint8_t BUTTONS_FOR_DIR[8] = {
    J_UP,             /* DIR_T  */
    J_UP | J_RIGHT,   /* DIR_RT */
    J_RIGHT,          /* DIR_R  */
    J_DOWN | J_RIGHT, /* DIR_RB */
    J_DOWN,           /* DIR_B  */
    J_DOWN | J_LEFT,  /* DIR_LB */
    J_LEFT,           /* DIR_L  */
    J_UP | J_LEFT,    /* DIR_LT */
};

/* input/prev_input globals defined in tests/mocks/input_globals.c */

void setUp(void) {
    input = 0;
    prev_input = 0;
    mock_vram_clear();
    camera_init(88, 720);  /* cam_y = 648 */
    player_init(0u);
    player_set_pos(88, 720);  /* track start: col 11, row 90 — road */
}
void tearDown(void) {}

/* --- AC1: acceleration reaches max speed -------------------------------- */

/* Holding J_RIGHT | J_A: X friction is 0 while J_RIGHT pressed, so vx accumulates
 * through gear1 (accel=2) then gear2 (accel=1) then gear3 (accel=1), reaching 6. */
void test_accel_reaches_max_speed(void) {
    uint8_t i;
    player_set_dir(DIR_R);
    input = J_RIGHT | J_A;
    for (i = 0u; i < 5u; i++) player_update();
    TEST_ASSERT_EQUAL_INT8(6, player_get_vx());
}

/* --- AC2: velocity capped at max speed ---------------------------------- */

/* Extra frames beyond gear3 max do not exceed 6. */
void test_accel_capped_at_max_speed(void) {
    uint8_t i;
    player_set_dir(DIR_R);
    input = J_RIGHT | J_A;
    for (i = 0u; i < 6u; i++) player_update();
    TEST_ASSERT_EQUAL_INT8(6, player_get_vx());
}

/* --- AC3: friction decelerates to zero ---------------------------------- */

/* Releasing direction from vx=6 (gear3 max) reaches vx==0 in 6 friction frames. */
void test_friction_decelerates_to_zero(void) {
    uint8_t i;
    player_set_dir(DIR_R);
    input = J_RIGHT | J_A;
    for (i = 0u; i < 5u; i++) player_update();  /* reach gear3 max */
    input = 0;
    for (i = 0u; i < 6u; i++) player_update();  /* friction: 6→5→4→3→2→1→0 */
    TEST_ASSERT_EQUAL_INT8(0, player_get_vx());
}

/* --- AC4: wall collision zeros vx, not vy ------------------------------- */

/* Row 90 (y=720) road: cols 6-17 (x=48-143). Right wall at col 18 (x=144+).
 * 16x16 hitbox: right corner = px+15.
 * Player at px=128: corner px+15=143 (col 17 = road).
 * Moving right (gas): new_px=129, corner=144 (col 18 = sand) → blocked → vx=0. */
void test_wall_zeros_vx_not_vy(void) {
    player_set_pos(128, 720);
    player_set_dir(DIR_RT);
    input = J_RIGHT | J_UP;  /* face NE, gas → vx blocked by wall, vy moves */
    player_update();
    TEST_ASSERT_EQUAL_INT8(0,              player_get_vx()); /* wall blocks x */
    TEST_ASSERT_EQUAL_INT8(-2, player_get_vy()); /* gear1 accel=2 in UP direction */
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

/* NE facing + gas: both axes reach gear3 max (6) in 5 frames. */
void test_x_and_y_axes_accumulate_independently(void) {
    uint8_t i;
    player_set_dir(DIR_RT);
    input = J_RIGHT | J_UP;
    for (i = 0u; i < 5u; i++) {
        player_update();
    }
    TEST_ASSERT_EQUAL_INT8( 6, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(-6, player_get_vy());
}

/* Player cannot move past map bottom boundary (active_map_h*8 - 8 = 792).
 * Player at py=792: moving down → new_py=793 > 792 → map clamp blocks. */
void test_y_clamped_at_map_bottom(void) {
    player_set_pos(88, 792);  /* py at map bottom boundary */
    player_set_dir(DIR_B);
    input = J_DOWN;
    player_update();           /* new_py=793 > active_map_h*8-8=792 → blocked */
    TEST_ASSERT_TRUE(player_get_y() <= 792);
}

/* --- Gear system tests (Issue #252) ------------------------------------ */

/* AC1a: After 1 frame from rest, speed = 2 → instantaneous shift to gear 2.
 * Gear 2 accel = 1, so frame 2 adds 1 → vx = 3.
 * If still gear 1: vx would be clamped at 2 (gear1 max). */
void test_gear_shifts_to_gear2_after_reaching_threshold(void) {
    player_set_dir(DIR_R);
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear1: vx=2, shifts to gear2 */
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear2: vx=3 */
    TEST_ASSERT_EQUAL_INT8(3, player_get_vx());
}

/* AC1b: Full progression gear1→2→3 in 5 frames.
 * Frame 1: gear1 accel=2, vx=2, shift to gear2.
 * Frames 2-3: gear2 accel=1, vx=3,4, shift to gear3.
 * Frames 4-5: gear3 accel=1, vx=5,6 (capped at gear3 max=6). */
void test_gear_reaches_gear3_max_speed_in_5_frames(void) {
    uint8_t i;
    player_set_dir(DIR_R);
    input = J_RIGHT;
    for (i = 0u; i < 5u; i++) player_update();
    TEST_ASSERT_EQUAL_INT8(6, player_get_vx());
}

/* AC2a: Downshift hysteresis — gear2 does NOT downshift immediately on low speed.
 * Drive to gear2 (vx=3), then coast:
 *   coast frame 1: vx=2, speed=2, NOT < 2 threshold, timer=0.
 *   coast frame 2: vx=1, speed=1 < 2, timer=1.
 *   coast frames 3-4: vx=0, timer=2,3.
 * After 4 coast frames (timer=3, < 8): still in gear2.
 * Next gas frame: gear2 accel=1, vx=0+1=1.
 * If downshifted to gear1: vx=0+2=2. */
void test_gear_does_not_downshift_before_8_frames(void) {
    uint8_t i;
    player_set_dir(DIR_R);
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear1→gear2, vx=2 */
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear2, vx=3 */
    for (i = 0u; i < 4u; i++) player_apply_physics(0, TILE_ROAD); /* coast */
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* still gear2: accel=1, vx=0+1=1 */
    TEST_ASSERT_EQUAL_INT8(1, player_get_vx());
}

/* AC2b: After exactly 8 frames below threshold, gear2 downshifts to gear1.
 * Drive to gear2 (vx=3), then coast:
 *   coast 1: vx=2, speed=2 NOT < 2, timer=0.
 *   coast 2: vx=1, speed=1 < 2, timer=1.
 *   coast 3-9 (7 more): vx=0, timer=2..8 → downshift fires at timer=8.
 * Total coast: 9 frames. Then gas: gear1 accel=2, vx=0+2=2.
 * If still gear2: vx=0+1=1. */
void test_gear2_downshifts_to_gear1_after_8_frames(void) {
    uint8_t i;
    player_set_dir(DIR_R);
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear1→gear2, vx=2 */
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear2, vx=3 */
    for (i = 0u; i < 9u; i++) player_apply_physics(0, TILE_ROAD); /* coast 9 frames */
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear1 now: accel=2, vx=2 */
    TEST_ASSERT_EQUAL_INT8(2, player_get_vx());
}

/* AC3: Wall collision resets gear to 1.
 * Build gear2, then hit wall. After wall collision, gear resets.
 * Wall collision happens in player_update() when move is blocked.
 * After reset: gear1 accel=2. From vx=0: next frame vx=2.
 * If gear2 (no reset): vx=0+1=1. */
void test_gear_resets_on_wall_collision(void) {
    /* Build gear2 via player_apply_physics */
    player_set_dir(DIR_R);
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear1→gear2, vx=2 */
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear2, vx=3 */
    /* Hit right wall: px=128, col 17 is road, col 18 is off-track */
    player_set_pos(128, 720);
    input = J_RIGHT | J_UP;  /* NE: x blocked by wall → vx=0, gear resets */
    player_update();
    /* vx=0 after wall. Verify gear1 accel via player_apply_physics */
    player_apply_physics(J_RIGHT, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8(2, player_get_vx());
}

/* AC4: Entering oil terrain resets gear to 1.
 * Reach gear3 (vx=6). Oil frame: gear resets to 0, max_speed becomes
 * GEAR1_MAX_SPEED=2, clamps vx from 6 to 2.
 * If no reset (gear3, max=6): vx stays 6. */
void test_gear_resets_on_oil(void) {
    uint8_t i;
    player_set_dir(DIR_R);
    for (i = 0u; i < 5u; i++) player_apply_physics(J_RIGHT, TILE_ROAD); /* gear3, vx=6 */
    player_apply_physics(0, TILE_OIL);   /* gear reset: vx clamped to gear1 max=2 */
    TEST_ASSERT_EQUAL_INT8(2, player_get_vx());
}

/* AC5: player_reset_vel() (respawn path) resets gear to 1.
 * Build gear2, then respawn. After respawn: gear1 accel=2.
 * From vx=0: next frame vx=2. If gear2: vx=1. */
void test_gear_resets_on_respawn(void) {
    player_set_dir(DIR_R);
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear1→gear2, vx=2 */
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gear2, vx=3 */
    player_reset_vel();                          /* vx=0, gear=0, timer=0 */
    player_apply_physics(J_RIGHT, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8(2, player_get_vx());
}

/* --- AC1: one notch per turn tick, clockwise ---------------------------- */

/* Facing north and holding RIGHT, the car reaches NE on the first turn tick and
 * E on the second. It is never E on frame 1 — that is the whole feature. */
void test_turn_right_steps_through_northeast(void) {
    uint8_t i;
    player_set_dir(DIR_T);

    player_apply_physics(J_RIGHT, TILE_ROAD);
    TEST_ASSERT_TRUE(player_get_dir() != DIR_R);          /* not east on frame 1 */

    for (i = 1u; i < TURN_PERIOD; i++) player_apply_physics(J_RIGHT, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT(DIR_RT, player_get_dir());      /* first tick  */

    for (i = 0u; i < TURN_PERIOD; i++) player_apply_physics(J_RIGHT, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT(DIR_R,  player_get_dir());      /* second tick */
}

/* --- AC2: the sweep takes the short way round --------------------------- */

/* Facing north and holding LEFT, the car turns counter-clockwise through NW and
 * reaches W. It never passes through E. */
void test_turn_left_takes_the_short_way_through_northwest(void) {
    uint8_t i;
    uint8_t saw_east = 0u;
    uint8_t saw_northwest = 0u;

    player_set_dir(DIR_T);
    for (i = 0u; i < (uint8_t)(2u * TURN_PERIOD); i++) {
        player_apply_physics(J_LEFT, TILE_ROAD);
        if (player_get_dir() == DIR_R)  saw_east = 1u;
        if (player_get_dir() == DIR_LT) saw_northwest = 1u;
    }
    TEST_ASSERT_EQUAL_UINT8(1u, saw_northwest);
    TEST_ASSERT_EQUAL_UINT8(0u, saw_east);
    TEST_ASSERT_EQUAL_INT(DIR_L, player_get_dir());
}

/* --- AC3: a half turn completes, and never leaves the eight-value ring --- */

/* Values 8-15 are turret-only. The sprite tables, the hitbox tables and DIR_DX/DY
 * are all 8 wide, so a facing above DIR_LT would index past the end of three
 * tables at once. Check every intermediate value, not just the last one.
 *
 * The first assertion is what makes this a regression test rather than a
 * statement of fact: without it the whole test passes against instant facing,
 * because a car that snaps to south on frame 1 also never leaves the ring and
 * also ends up facing south. It is vacuous only at PLAYER_HANDLING == 7, where
 * the period is one frame and a single step is the correct answer. */
void test_half_turn_completes_and_stays_in_the_eight_ring(void) {
    uint8_t i;

    player_set_dir(DIR_T);
    player_apply_physics(J_DOWN, TILE_ROAD);
#if PLAYER_HANDLING < 7
    TEST_ASSERT_TRUE(player_get_dir() != DIR_B);     /* not south on frame 1 */
#endif

    player_set_dir(DIR_T);
    for (i = 0u; i < (uint8_t)(4u * TURN_PERIOD); i++) {
        player_apply_physics(J_DOWN, TILE_ROAD);
        TEST_ASSERT_TRUE(player_get_dir() <= DIR_LT);
    }
    TEST_ASSERT_EQUAL_INT(DIR_B, player_get_dir());
}

/* The 180 degree tie resolves clockwise, and does so from every facing — R2 allows
 * either way round but demands it be the same way every time. */
void test_half_turn_tie_always_resolves_clockwise(void) {
    uint8_t d;
    for (d = 0u; d < 8u; d++) {
        uint8_t i;
        player_set_dir((player_dir_t)d);
        for (i = 0u; i < TURN_PERIOD; i++) {
            player_apply_physics(BUTTONS_FOR_DIR[(d + 4u) & 7u], TILE_ROAD);
        }
        TEST_ASSERT_EQUAL_INT((player_dir_t)((d + 1u) & 7u), player_get_dir());
    }
}

/* --- AC4: releasing the D-pad freezes the facing ------------------------ */

/* One notch into a half turn, let go. The facing stays where it reached and does
 * not keep rotating, however long the car coasts. */
void test_release_mid_sweep_freezes_the_facing(void) {
    uint8_t i;
    player_dir_t reached;

    player_set_dir(DIR_T);
    for (i = 0u; i < TURN_PERIOD; i++) player_apply_physics(J_DOWN, TILE_ROAD);
    reached = player_get_dir();
    TEST_ASSERT_EQUAL_INT(DIR_RT, reached);

    for (i = 0u; i < (uint8_t)(4u * TURN_PERIOD); i++) player_apply_physics(0, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT(reached, player_get_dir());
}

/* A request that already matches the facing turns nothing and costs nothing.
 * This one passes on the old code too — it pins a property, it is not evidence
 * for the feature. Do not count it toward an acceptance criterion. */
void test_request_matching_the_facing_does_not_turn(void) {
    uint8_t i;
    player_set_dir(DIR_R);
    for (i = 0u; i < (uint8_t)(4u * TURN_PERIOD); i++) {
        player_apply_physics(J_RIGHT, TILE_ROAD);
        TEST_ASSERT_EQUAL_INT(DIR_R, player_get_dir());
    }
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
    RUN_TEST(test_gear_shifts_to_gear2_after_reaching_threshold);
    RUN_TEST(test_gear_reaches_gear3_max_speed_in_5_frames);
    RUN_TEST(test_gear_does_not_downshift_before_8_frames);
    RUN_TEST(test_gear2_downshifts_to_gear1_after_8_frames);
    RUN_TEST(test_gear_resets_on_wall_collision);
    RUN_TEST(test_gear_resets_on_oil);
    RUN_TEST(test_gear_resets_on_respawn);
    RUN_TEST(test_turn_right_steps_through_northeast);
    RUN_TEST(test_turn_left_takes_the_short_way_through_northwest);
    RUN_TEST(test_half_turn_completes_and_stays_in_the_eight_ring);
    RUN_TEST(test_half_turn_tie_always_resolves_clockwise);
    RUN_TEST(test_release_mid_sweep_freezes_the_facing);
    RUN_TEST(test_request_matching_the_facing_does_not_turn);
    return UNITY_END();
}
