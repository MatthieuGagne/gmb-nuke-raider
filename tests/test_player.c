#include "unity.h"
#include <gb/gb.h>
#include "../src/input.h"
#include "player.h"
#include "camera.h"
#include "../src/damage.h"

/* input/prev_input globals defined in tests/mocks/input_globals.c */

void setUp(void) {
    input = 0;
    prev_input = 0;
    mock_vram_clear();
    mock_move_sprite_reset();
    camera_init(88, 720);  /* cam_y = 648 */
    damage_init();
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
    input = J_LEFT | J_A;
    player_update();
    TEST_ASSERT_EQUAL_INT16(87, player_get_x());
}

void test_player_update_moves_right(void) {
    input = J_RIGHT | J_A;
    player_update();
    TEST_ASSERT_EQUAL_INT16(89, player_get_x());
}

void test_player_update_moves_up(void) {
    input = J_UP | J_A;
    player_update();
    TEST_ASSERT_EQUAL_INT16(719, player_get_y());
}

void test_player_update_moves_down(void) {
    input = J_B;   /* B while stopped = reverse (backward = positive vy) */
    player_update();
    TEST_ASSERT_EQUAL_INT16(721, player_get_y());
}

/* --- track collision (new map geometry) -------------------------------- */

/* Left wall: tile col 3 (x=24-31) is off-track for rows 0-49 */
void test_player_blocked_by_left_wall(void) {
    player_set_pos(32, 80);   /* leftmost road tile (col 4, x=32) */
    input = J_LEFT | J_A;
    player_update();          /* new_px=31 -> col 3 -> off-track -> blocked */
    TEST_ASSERT_EQUAL_INT16(32, player_get_x());
}

/* Right wall: corner px+7=128 -> tile col 16 -> off-track */
void test_player_blocked_by_right_wall(void) {
    player_set_pos(120, 80);  /* rightmost safe: corner at 127 (col 15, road) */
    input = J_RIGHT | J_A;
    player_update();          /* new_px=121 -> corner at 128 (col 16) -> off-track */
    TEST_ASSERT_EQUAL_INT16(120, player_get_x());
}

/* --- screen X clamp [0, 159] ------------------------------------------- */

void test_player_clamped_at_screen_left(void) {
    player_set_pos(0, 80);
    input = J_LEFT | J_A;
    player_update();          /* new_px=-1 < 0 -> blocked */
    TEST_ASSERT_EQUAL_INT16(0, player_get_x());
}

void test_player_clamped_at_screen_right(void) {
    player_set_pos(159, 80);
    input = J_RIGHT | J_A;
    player_update();          /* new_px=160 > 159 -> blocked */
    TEST_ASSERT_EQUAL_INT16(159, player_get_x());
}

/* --- screen Y clamp [cam_y, cam_y+143] ---------------------------------- */

/* cam_y=648. Player at py=648 (top of screen). Track at (80,647) IS passable
 * (col 10, row 80 = road), so ONLY screen clamp prevents upward movement. */
void test_player_clamped_at_screen_top(void) {
    player_set_pos(80, 648);  /* py == cam_y: at top of viewport */
    input = J_UP | J_A;
    player_update();          /* new_py=647 < cam_y=648 -> blocked */
    TEST_ASSERT_EQUAL_INT16(648, player_get_y());
}

/* cam_y=648, cam_y+143=791. Track at (80,792) IS passable (col 10, row 99 = road),
 * so ONLY screen clamp prevents downward movement past screen bottom. */
void test_player_clamped_at_screen_bottom(void) {
    player_set_pos(80, 791);  /* py beyond HUD clamp (cam_y+112=760) */
    input = J_A;              /* gas tries to move up to 790, still > 760 -> blocked */
    player_update();
    TEST_ASSERT_EQUAL_INT16(791, player_get_y());
}

/* --- sprite slot count -------------------------------------------------- */

void test_player_init_claims_two_sprite_slots(void) {
    /* setUp called player_init(); it should have claimed slots 0 and 1.
     * The next free slot must be 2. */
    uint8_t next = get_sprite();
    TEST_ASSERT_EQUAL_UINT8(2u, next);
}

/* --- two-sprite render -------------------------------------------------- */

void test_player_render_calls_move_sprite_twice(void) {
    mock_move_sprite_reset();
    player_render();
    TEST_ASSERT_EQUAL_INT(2, mock_move_sprite_call_count);
}

void test_player_render_both_halves_aligned(void) {
    /* Both halves must share the same X; bottom half must be exactly 8px lower. */
    mock_move_sprite_reset();
    player_render();
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_x[0], mock_sprite_x[1]);
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_y[0] + 8u, mock_sprite_y[1]);
}

/* ===== Gas / Brake / Facing tests (issue #132) ============================= */

/* AC5: D-pad UP/DOWN have no effect on velocity — only A/B control Y axis */
void test_dpad_up_down_does_not_change_velocity(void) {
    player_apply_physics(J_UP,   TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8(0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(0, player_get_vy());
    player_apply_physics(J_DOWN, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8(0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(0, player_get_vy());
}

/* AC1: J_A (gas) accelerates in the current facing direction.
 * setUp calls player_init() which sets facing = up (dy=-1).
 * Gas should give vy = -1. */
void test_gas_while_facing_up_decreases_vy(void) {
    player_apply_physics(J_A, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8( 0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(-1, player_get_vy());
}

/* AC1: A always moves forward (negative vy) even when D-pad down is held.
 * D-pad direction does not affect A/B axis. */
void test_gas_always_moves_forward_regardless_of_dpad(void) {
    player_apply_physics(J_DOWN | J_A, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8( 0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(-1, player_get_vy());
}

/* AC4: J_B while stopped reverses in the direction opposite to facing.
 * Default facing = up (dy=-1), so reverse = vy += 1. */
void test_brake_while_stopped_facing_up_reverses_down(void) {
    player_apply_physics(J_B, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8(0,  player_get_vx());
    TEST_ASSERT_EQUAL_INT8(1,  player_get_vy());
}

/* AC4: B while moving decelerates — never reverses lateral direction.
 * Steer right (vx=1), then B: coast friction + brake. vx must not go negative. */
void test_brake_while_moving_laterally_does_not_reverse_x(void) {
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* vx = 1 */
    player_apply_physics(J_B,     TILE_ROAD);   /* not stopped: brake, coast clears vx */
    TEST_ASSERT_GREATER_OR_EQUAL_INT8(0, player_get_vx());
}

/* --- flicker: HP > 2 = no hide --- */
void test_render_at_full_hp_calls_move_sprite_normally(void) {
    /* setUp calls damage_init → full HP */
    mock_move_sprite_reset();
    player_render();
    /* Both halves must be placed on-screen (y > 0) */
    TEST_ASSERT_GREATER_THAN_UINT8(0u, mock_sprite_y[0]);
    TEST_ASSERT_GREATER_THAN_UINT8(0u, mock_sprite_y[1]);
}

/* --- flicker: HP <= 2, frame counter bit 3 set = hide --- */
void test_render_at_low_hp_hides_on_flicker_frame(void) {
    uint8_t i;
    /* Force hp to 1 */
    damage_init();
    damage_apply((uint8_t)(PLAYER_MAX_HP - 1u));  /* hp = 1 */
    /* Burn 30 frames of i-frames */
    for (i = 0u; i < DAMAGE_INVINCIBILITY_FRAMES; i++) damage_tick();
    /* Call render 8 times (frame counter = 0..7, bit3 = 0: visible)
     * then 1 more (frame counter = 8, bit3 = 1: hidden) */
    for (i = 0u; i < 8u; i++) player_render();
    mock_move_sprite_reset();
    player_render();  /* frame_counter == 8, bit3 set → hide */
    TEST_ASSERT_EQUAL_UINT8(0u, mock_sprite_y[0]);
    TEST_ASSERT_EQUAL_UINT8(0u, mock_sprite_y[1]);
}

/* --- flicker: HP <= 2, frame counter bit 3 clear = visible --- */
void test_render_at_low_hp_visible_on_non_flicker_frame(void) {
    uint8_t i;
    damage_init();
    damage_apply((uint8_t)(PLAYER_MAX_HP - 1u));
    for (i = 0u; i < DAMAGE_INVINCIBILITY_FRAMES; i++) damage_tick();
    /* frame_counter=0 at init, bit3=0: visible */
    mock_move_sprite_reset();
    player_render();
    TEST_ASSERT_GREATER_THAN_UINT8(0u, mock_sprite_y[0]);
}

/* --- repair tile healing ------------------------------------------------ */

/* Tests damage_heal directly — TILE_REPAIR integration is verified in smoketest
 * (requires map edit; mock track returns TILE_ROAD for all road coordinates). */
void test_heal_call_restores_hp(void) {
    uint8_t i;
    damage_init();
    damage_apply(3u);                              /* hp = PLAYER_MAX_HP - 3 */
    for (i = 0u; i < DAMAGE_INVINCIBILITY_FRAMES; i++) damage_tick();
    damage_heal(DAMAGE_REPAIR_AMOUNT);             /* hp += 2 */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

/* AC3: J_B while moving must NOT reverse the car. */
void test_brake_while_moving_does_not_reverse(void) {
    player_apply_physics(J_RIGHT | J_A, TILE_ROAD);  /* vx = 1 */
    player_apply_physics(J_B,           TILE_ROAD);  /* brake, not reverse */
    /* vx must not go negative */
    TEST_ASSERT_GREATER_OR_EQUAL_INT8(0, player_get_vx());
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
    RUN_TEST(test_player_init_claims_two_sprite_slots);
    RUN_TEST(test_player_render_calls_move_sprite_twice);
    RUN_TEST(test_player_render_both_halves_aligned);
    RUN_TEST(test_dpad_up_down_does_not_change_velocity);
    RUN_TEST(test_gas_while_facing_up_decreases_vy);
    RUN_TEST(test_gas_always_moves_forward_regardless_of_dpad);
    RUN_TEST(test_brake_while_stopped_facing_up_reverses_down);
    RUN_TEST(test_brake_while_moving_laterally_does_not_reverse_x);
    RUN_TEST(test_brake_while_moving_does_not_reverse);
    RUN_TEST(test_render_at_full_hp_calls_move_sprite_normally);
    RUN_TEST(test_render_at_low_hp_hides_on_flicker_frame);
    RUN_TEST(test_render_at_low_hp_visible_on_non_flicker_frame);
    RUN_TEST(test_heal_call_restores_hp);
    return UNITY_END();
}
