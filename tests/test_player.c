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
    camera_init(88, 8);  /* cam_y = 0 (clamped) */
    damage_init();
    player_init();
}
void tearDown(void) {}

/* --- start position ---------------------------------------------------- */

void test_player_init_sets_start_position(void) {
    TEST_ASSERT_EQUAL_INT16(88, player_get_x());
    TEST_ASSERT_EQUAL_INT16(8, player_get_y());
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
    TEST_ASSERT_EQUAL_INT16(7, player_get_y());
}

void test_player_update_moves_down(void) {
    input = J_DOWN;  /* face south + gas → moves south (+vy) */
    player_update();
    TEST_ASSERT_EQUAL_INT16(9, player_get_y());
}

/* --- track collision (new map geometry) -------------------------------- */

/* Left wall: tile col 3 (x=24-31) is off-track for rows 0-49 */
void test_player_blocked_by_left_wall(void) {
    player_set_pos(32, 80);   /* leftmost road tile (col 4, x=32) */
    input = J_LEFT | J_A;
    player_update();          /* new_px=31 -> col 3 -> off-track -> blocked */
    TEST_ASSERT_EQUAL_INT16(32, player_get_x());
}

/* Right wall: 16px hitbox — right corner = px+15. Road ends before col 16 (x=128). */
void test_player_blocked_by_right_wall_16px(void) {
    /* px=112: right corner = 127 (col 15, road). Moving right: corner=128 -> off-track */
    player_set_pos(112, 80);
    input = J_RIGHT | J_A;
    player_update();
    TEST_ASSERT_EQUAL_INT16(112, player_get_x());
}

/* --- screen X clamp [0, 144] (= 160-16) ----------------------------------- */

void test_player_clamped_at_screen_left(void) {
    player_set_pos(0, 80);
    input = J_LEFT | J_A;
    player_update();          /* new_px=-1 < 0 -> blocked */
    TEST_ASSERT_EQUAL_INT16(0, player_get_x());
}

void test_player_clamped_at_screen_right_16px(void) {
    player_set_pos(144, 80);
    input = J_RIGHT | J_A;
    player_update();          /* new_px=145 > 144 -> blocked */
    TEST_ASSERT_EQUAL_INT16(144, player_get_x());
}

/* --- map Y clamp [0, MAP_PX_H-16] ---------------------------------------- */

/* Map-bounds clamp: player can now move below cam_y; track at (80,647) IS
 * passable (col 10, row 80 = road), so player moves freely to 647. */
void test_player_moves_below_old_screen_top(void) {
    player_set_pos(80, 648);  /* py == old cam_y: was blocked by screen clamp */
    input = J_UP | J_A;
    player_update();          /* new_py=647 >= 0, passable -> allowed */
    TEST_ASSERT_EQUAL_INT16(647, player_get_y());
}

/* Map-bounds clamp: 16px hitbox — bottom boundary is MAP_PX_H-16. */
void test_player_clamped_at_bottom_map_bound_16px(void) {
    player_set_pos(80, (int16_t)(MAP_PX_H - 16u));
    input = J_DOWN;
    player_update();          /* new_py = MAP_PX_H-15 > MAP_PX_H-16 -> blocked */
    TEST_ASSERT_EQUAL_INT16((int16_t)(MAP_PX_H - 16u), player_get_y());
}

void test_player_moves_near_bottom_map_bound(void) {
    /* MAP_PX_H-15: moving north sets new_py=MAP_PX_H-16, within bounds -> allowed */
    player_set_pos(80, (int16_t)(MAP_PX_H - 15u));
    input = J_UP;
    player_update();
    TEST_ASSERT_EQUAL_INT16((int16_t)(MAP_PX_H - 16u), player_get_y());
}

/* --- sprite slot count -------------------------------------------------- */

void test_player_init_claims_four_sprite_slots(void) {
    /* setUp called player_init(); it should have claimed slots 0-3.
     * The next free slot must be 4. */
    uint8_t next = get_sprite();
    TEST_ASSERT_EQUAL_UINT8(4u, next);
}

/* --- four-sprite render -------------------------------------------------- */

void test_player_render_calls_move_sprite_four_times(void) {
    mock_move_sprite_reset();
    player_render();
    TEST_ASSERT_EQUAL_INT(4, mock_move_sprite_call_count);
}

void test_player_render_2x2_grid_layout(void) {
    /* TL and BL share same X; TR and BR share same X = TL_x + 8.
     * TL and TR share same Y; BL and BR share same Y = TL_y + 8. */
    mock_move_sprite_reset();
    player_render();
    /* Slots: 0=TL, 1=BL, 2=TR, 3=BR */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_x[0], mock_sprite_x[1]);           /* TL.x == BL.x */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_x[2], mock_sprite_x[3]);           /* TR.x == BR.x */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_x[0] + 8u, mock_sprite_x[2]);     /* TR.x == TL.x+8 */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_y[0], mock_sprite_y[2]);           /* TL.y == TR.y */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_y[1], mock_sprite_y[3]);           /* BL.y == BR.y */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_y[0] + 8u, mock_sprite_y[1]);     /* BL.y == TL.y+8 */
}

/* ===== Gas / Brake / Facing tests (issue #132) ============================= */

/* B button is unbound — must not change velocity */
void test_b_button_does_not_change_velocity(void) {
    player_apply_physics(J_B, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8(0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(0, player_get_vy());
}

/* AC1: J_UP: face north + gas → vy = -1. */
void test_gas_while_facing_up_decreases_vy(void) {
    player_apply_physics(J_UP, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8( 0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(-1, player_get_vy());
}

/* UP+RIGHT=NE facing + gas: both axes get ACCEL simultaneously */
void test_gas_diagonal_dpad_applies_diagonal_vector(void) {
    player_apply_physics(J_RIGHT | J_UP, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8( 1, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(-1, player_get_vy());
}

/* Face south + gas = move south */
void test_brake_while_stopped_facing_up_reverses_down(void) {
    player_apply_physics(J_DOWN, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8(0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(1, player_get_vy());
}

/* Gas east (vx=1), then gas south: friction on vx — must not reverse. */
void test_brake_while_moving_laterally_does_not_reverse_x(void) {
    player_apply_physics(J_RIGHT, TILE_ROAD);   /* gas east: vx=1 */
    player_apply_physics(J_DOWN,  TILE_ROAD);   /* gas south: friction on vx */
    TEST_ASSERT_GREATER_OR_EQUAL_INT8(0, player_get_vx());
}

/* --- flicker: HP > 2 = no hide --- */
void test_render_at_full_hp_calls_move_sprite_normally(void) {
    /* setUp calls damage_init → full HP */
    mock_move_sprite_reset();
    player_render();
    /* All 4 OAM slots must be placed on-screen (y > 0) */
    TEST_ASSERT_GREATER_THAN_UINT8(0u, mock_sprite_y[0]);
    TEST_ASSERT_GREATER_THAN_UINT8(0u, mock_sprite_y[1]);
    TEST_ASSERT_GREATER_THAN_UINT8(0u, mock_sprite_y[2]);
    TEST_ASSERT_GREATER_THAN_UINT8(0u, mock_sprite_y[3]);
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
    player_render();  /* frame_counter == 8, bit3 set → hide all 4 slots */
    TEST_ASSERT_EQUAL_UINT8(0u, mock_sprite_y[0]);
    TEST_ASSERT_EQUAL_UINT8(0u, mock_sprite_y[1]);
    TEST_ASSERT_EQUAL_UINT8(0u, mock_sprite_y[2]);
    TEST_ASSERT_EQUAL_UINT8(0u, mock_sprite_y[3]);
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
    TEST_ASSERT_GREATER_THAN_UINT8(0u, mock_sprite_y[3]);
}

/* --- repair tile healing ------------------------------------------------ */

/* Tests damage_heal directly — TILE_REPAIR integration is verified in smoketest
 * (requires map edit; mock track returns TILE_ROAD for all road coordinates). */
void test_heal_call_restores_hp(void) {
    uint8_t i;
    damage_init();
    damage_apply(21u);                             /* hp = PLAYER_MAX_HP - 21 = 79 */
    for (i = 0u; i < DAMAGE_INVINCIBILITY_FRAMES; i++) damage_tick();
    damage_heal(DAMAGE_REPAIR_AMOUNT);             /* hp += 20 → 99 */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

/* Gas NE (vx=1, vy=-1), then gas south: vy toward +1, vx friction'd — must not reverse. */
void test_brake_while_moving_does_not_reverse(void) {
    player_apply_physics(J_RIGHT | J_UP, TILE_ROAD);  /* gas NE: vx=1, vy=-1 */
    player_apply_physics(J_DOWN,         TILE_ROAD);  /* gas S: vy toward +1 */
    TEST_ASSERT_GREATER_OR_EQUAL_INT8(0, player_get_vx());
}

/* ===== 8-directional facing (issue #133) ============================= */

/* Helper: reset velocity, apply one physics frame, check direction */
static void apply_and_check_dir(uint8_t buttons, player_dir_t expected) {
    player_reset_vel();
    player_apply_physics(buttons, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT(expected, player_get_dir());
}

/* AC1: each D-pad combo maps to the correct facing direction */
void test_dir_up_sets_T(void)          { apply_and_check_dir(J_UP,            DIR_T);  }
void test_dir_up_right_sets_RT(void)   { apply_and_check_dir(J_UP | J_RIGHT,  DIR_RT); }
void test_dir_right_sets_R(void)       { apply_and_check_dir(J_RIGHT,          DIR_R);  }
void test_dir_down_right_sets_RB(void) { apply_and_check_dir(J_DOWN | J_RIGHT, DIR_RB); }
void test_dir_down_sets_B(void)        { apply_and_check_dir(J_DOWN,           DIR_B);  }
void test_dir_down_left_sets_LB(void)  { apply_and_check_dir(J_DOWN | J_LEFT,  DIR_LB); }
void test_dir_left_sets_L(void)        { apply_and_check_dir(J_LEFT,            DIR_L);  }
void test_dir_up_left_sets_LT(void)    { apply_and_check_dir(J_UP | J_LEFT,    DIR_LT); }

/* AC1: no D-pad held preserves last direction */
void test_dir_no_dpad_keeps_last(void) {
    player_apply_physics(J_RIGHT, TILE_ROAD);  /* set facing = R */
    player_apply_physics(0,       TILE_ROAD);  /* no dpad: keep R */
    TEST_ASSERT_EQUAL_INT(DIR_R, player_get_dir());
}

/* AC2: A + each facing direction applies correct velocity vector */

/* DIR_T (North): dx=0, dy=-ACCEL → vx=0, vy=-1 */
void test_gas_facing_T_moves_north(void) {
    player_apply_physics(J_UP, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8( 0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(-1, player_get_vy());
}

/* DIR_RT (NE): dx=+ACCEL, dy=-ACCEL → vx=1, vy=-1 */
void test_gas_facing_RT_moves_northeast(void) {
    player_apply_physics(J_UP | J_RIGHT, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8( 1, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(-1, player_get_vy());
}

/* DIR_R (East): dx=+ACCEL, dy=0 → vx=1, vy=0 */
void test_gas_facing_R_moves_east(void) {
    player_apply_physics(J_RIGHT, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8( 1, player_get_vx());
    TEST_ASSERT_EQUAL_INT8( 0, player_get_vy());
}

/* DIR_RB (SE): dx=+ACCEL, dy=+ACCEL → vx=1, vy=1 */
void test_gas_facing_RB_moves_southeast(void) {
    player_apply_physics(J_DOWN | J_RIGHT, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8( 1, player_get_vx());
    TEST_ASSERT_EQUAL_INT8( 1, player_get_vy());
}

/* DIR_B (South): dx=0, dy=+ACCEL → vx=0, vy=1 */
void test_gas_facing_B_moves_south(void) {
    player_apply_physics(J_DOWN, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8( 0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8( 1, player_get_vy());
}

/* DIR_LB (SW): dx=-ACCEL, dy=+ACCEL → vx=-1, vy=1 */
void test_gas_facing_LB_moves_southwest(void) {
    player_apply_physics(J_DOWN | J_LEFT, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8(-1, player_get_vx());
    TEST_ASSERT_EQUAL_INT8( 1, player_get_vy());
}

/* DIR_L (West): dx=-ACCEL, dy=0 → vx=-1, vy=0 */
void test_gas_facing_L_moves_west(void) {
    player_apply_physics(J_LEFT, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8(-1, player_get_vx());
    TEST_ASSERT_EQUAL_INT8( 0, player_get_vy());
}

/* DIR_LT (NW): dx=-ACCEL, dy=-ACCEL → vx=-1, vy=-1 */
void test_gas_facing_LT_moves_northwest(void) {
    player_apply_physics(J_UP | J_LEFT, TILE_ROAD);
    TEST_ASSERT_EQUAL_INT8(-1, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(-1, player_get_vy());
}

/* No D-pad: direction preserved but no gas — velocity stays at zero */
void test_no_dpad_preserves_dir_but_no_gas(void) {
    player_apply_physics(J_RIGHT, TILE_ROAD);  /* face R + gas east: vx=1 */
    player_reset_vel();
    player_apply_physics(0, TILE_ROAD);        /* no dpad: keep R, no gas */
    TEST_ASSERT_EQUAL_INT(DIR_R, player_get_dir());
    TEST_ASSERT_EQUAL_INT8(0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(0, player_get_vy());
}

/* Oil terrain disables gas */
void test_gas_disabled_on_oil(void) {
    player_apply_physics(J_UP, TILE_OIL);
    TEST_ASSERT_EQUAL_INT8(0, player_get_vx());
    TEST_ASSERT_EQUAL_INT8(0, player_get_vy());
}

void test_player_dir_dx_east(void) {
    TEST_ASSERT_EQUAL_INT8(1, player_dir_dx(DIR_R));
}

void test_player_dir_dx_west(void) {
    TEST_ASSERT_EQUAL_INT8(-1, player_dir_dx(DIR_L));
}

void test_player_dir_dy_north(void) {
    TEST_ASSERT_EQUAL_INT8(-1, player_dir_dy(DIR_T));
}

void test_player_dir_dy_south(void) {
    TEST_ASSERT_EQUAL_INT8(1, player_dir_dy(DIR_B));
}

/* --- direction → tile index mapping (16×16 2×2 grid) ------------------- */

void test_dir_T_tile_tl_is_up_base(void) {
    /* DIR_T: no flip, all 4 slots use PLAYER_TILE_UP_BASE + 0..3 */
    mock_move_sprite_reset();
    player_apply_physics(J_UP, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 0u, mock_sprite_tile[0]);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 1u, mock_sprite_tile[1]);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 2u, mock_sprite_tile[2]);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 3u, mock_sprite_tile[3]);
}

void test_dir_B_tile_tl_is_up_bl_with_flipy(void) {
    /* DIR_B = UP + FLIPY + row-swap: TL slot gets UP's BL tile, flip = S_FLIPY */
    mock_move_sprite_reset();
    player_apply_physics(J_DOWN, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 1u, mock_sprite_tile[0]); /* TL = UP BL */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 0u, mock_sprite_tile[1]); /* BL = UP TL */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 3u, mock_sprite_tile[2]); /* TR = UP BR */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 2u, mock_sprite_tile[3]); /* BR = UP TR */
    TEST_ASSERT_EQUAL_UINT8(S_FLIPY, mock_sprite_prop[0]);
}

void test_dir_L_tile_tl_is_right_tr_with_flipx(void) {
    /* DIR_L = RIGHT + FLIPX + col-swap: TL slot gets RIGHT's TR tile, flip = S_FLIPX */
    mock_move_sprite_reset();
    player_apply_physics(J_LEFT, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_RIGHT_BASE + 2u, mock_sprite_tile[0]); /* TL = R TR */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_RIGHT_BASE + 3u, mock_sprite_tile[1]); /* BL = R BR */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_RIGHT_BASE + 0u, mock_sprite_tile[2]); /* TR = R TL */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_RIGHT_BASE + 1u, mock_sprite_tile[3]); /* BR = R BL */
    TEST_ASSERT_EQUAL_UINT8(S_FLIPX, mock_sprite_prop[0]);
}

void test_dir_R_no_flip(void) {
    player_apply_physics(J_RIGHT, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(0u, mock_sprite_prop[0]);
}

void test_dir_RB_no_flip(void) {
    player_apply_physics(J_DOWN | J_RIGHT, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(0u, mock_sprite_prop[0]);
}

void test_dir_LB_flipx(void) {
    player_apply_physics(J_DOWN | J_LEFT, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(S_FLIPX, mock_sprite_prop[0]);
}

void test_dir_LT_flipx(void) {
    player_apply_physics(J_UP | J_LEFT, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(S_FLIPX, mock_sprite_prop[0]);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_player_init_sets_start_position);
    RUN_TEST(test_player_update_moves_left);
    RUN_TEST(test_player_update_moves_right);
    RUN_TEST(test_player_update_moves_up);
    RUN_TEST(test_player_update_moves_down);
    RUN_TEST(test_player_blocked_by_left_wall);
    RUN_TEST(test_player_blocked_by_right_wall_16px);
    RUN_TEST(test_player_clamped_at_screen_left);
    RUN_TEST(test_player_clamped_at_screen_right_16px);
    RUN_TEST(test_player_moves_below_old_screen_top);
    RUN_TEST(test_player_clamped_at_bottom_map_bound_16px);
    RUN_TEST(test_player_moves_near_bottom_map_bound);
    RUN_TEST(test_player_init_claims_four_sprite_slots);
    RUN_TEST(test_player_render_calls_move_sprite_four_times);
    RUN_TEST(test_player_render_2x2_grid_layout);
    RUN_TEST(test_b_button_does_not_change_velocity);
    RUN_TEST(test_gas_while_facing_up_decreases_vy);
    RUN_TEST(test_gas_diagonal_dpad_applies_diagonal_vector);
    RUN_TEST(test_brake_while_stopped_facing_up_reverses_down);
    RUN_TEST(test_brake_while_moving_laterally_does_not_reverse_x);
    RUN_TEST(test_brake_while_moving_does_not_reverse);
    RUN_TEST(test_render_at_full_hp_calls_move_sprite_normally);
    RUN_TEST(test_render_at_low_hp_hides_on_flicker_frame);
    RUN_TEST(test_render_at_low_hp_visible_on_non_flicker_frame);
    RUN_TEST(test_heal_call_restores_hp);
    /* AC1: direction facing */
    RUN_TEST(test_dir_up_sets_T);
    RUN_TEST(test_dir_up_right_sets_RT);
    RUN_TEST(test_dir_right_sets_R);
    RUN_TEST(test_dir_down_right_sets_RB);
    RUN_TEST(test_dir_down_sets_B);
    RUN_TEST(test_dir_down_left_sets_LB);
    RUN_TEST(test_dir_left_sets_L);
    RUN_TEST(test_dir_up_left_sets_LT);
    RUN_TEST(test_dir_no_dpad_keeps_last);
    /* AC2: direction → velocity vector */
    RUN_TEST(test_gas_facing_T_moves_north);
    RUN_TEST(test_gas_facing_RT_moves_northeast);
    RUN_TEST(test_gas_facing_R_moves_east);
    RUN_TEST(test_gas_facing_RB_moves_southeast);
    RUN_TEST(test_gas_facing_B_moves_south);
    RUN_TEST(test_gas_facing_LB_moves_southwest);
    RUN_TEST(test_gas_facing_L_moves_west);
    RUN_TEST(test_gas_facing_LT_moves_northwest);
    RUN_TEST(test_no_dpad_preserves_dir_but_no_gas);
    RUN_TEST(test_gas_disabled_on_oil);
    /* direction accessor */
    RUN_TEST(test_player_dir_dx_east);
    RUN_TEST(test_player_dir_dx_west);
    RUN_TEST(test_player_dir_dy_north);
    RUN_TEST(test_player_dir_dy_south);
    /* AC: direction → tile index and flip (16×16 2×2 grid) */
    RUN_TEST(test_dir_T_tile_tl_is_up_base);
    RUN_TEST(test_dir_B_tile_tl_is_up_bl_with_flipy);
    RUN_TEST(test_dir_L_tile_tl_is_right_tr_with_flipx);
    RUN_TEST(test_dir_R_no_flip);
    RUN_TEST(test_dir_RB_no_flip);
    RUN_TEST(test_dir_LB_flipx);
    RUN_TEST(test_dir_LT_flipx);
    return UNITY_END();
}
