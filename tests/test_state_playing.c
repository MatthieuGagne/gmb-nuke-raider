#include "unity.h"
#include "track.h"         /* TRACK_TYPE_RACE, TRACK_TYPE_COMBAT, CHECKPOINT_DIR_* */
#include "state_playing.h" /* finish_eval, cd_advance */
#include "../src/config.h"
#include "player.h"

/* Frame counts derive from the config.h table, never from a hardcoded number (#628). */
static const uint8_t TURN_FRAMES_T[8] = PLAYER_TURN_FRAMES_TABLE;
#define TURN_PERIOD  (TURN_FRAMES_T[PLAYER_HANDLING])

void setUp(void) {}
void tearDown(void) {}

/* finish_eval(map_type, armed, pdir, req_dir, finish_dir, cps_cleared) -> 1 = transition */

/* --- Race/combat gate tests (finish direction = S) --- */

void test_finish_eval_race_all_conditions_met(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_B, DIR_B, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_race_missing_checkpoint(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_B, DIR_B, CHECKPOINT_DIR_S, 0u));
}

void test_finish_eval_race_not_armed(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 0u, DIR_B, DIR_B, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_race_wrong_direction(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, DIR_T, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_combat_no_checkpoint_needed(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_COMBAT, 1u, DIR_B, DIR_B, CHECKPOINT_DIR_S, 0u));
}

void test_finish_eval_combat_not_armed(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_COMBAT, 0u, DIR_B, DIR_B, CHECKPOINT_DIR_S, 0u));
}

void test_finish_eval_combat_wrong_direction(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_COMBAT, 1u, DIR_T, DIR_T, CHECKPOINT_DIR_S, 0u));
}

/* --- Direction N: fires when facing north (DIR_T, DIR_RT, DIR_LT) --- */

void test_finish_eval_dir_N_valid(void) {
    /* facing north — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, DIR_T, CHECKPOINT_DIR_N, 1u));
}

void test_finish_eval_dir_N_invalid_zero(void) {
    /* facing east (no north component) — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, DIR_R, CHECKPOINT_DIR_N, 1u));
}

void test_finish_eval_dir_N_invalid_south(void) {
    /* facing south — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_B, DIR_B, CHECKPOINT_DIR_N, 1u));
}

/* --- Direction S: fires when facing south (DIR_B, DIR_RB, DIR_LB) --- */

void test_finish_eval_dir_S_valid(void) {
    /* facing south — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_B, DIR_B, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_dir_S_invalid_zero(void) {
    /* facing east (no south component) — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, DIR_R, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_dir_S_invalid_north(void) {
    /* facing north — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, DIR_T, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_dir_S_racer_blocked_still_counts(void) {
    /* Regression #382: diagonal SW approach still counts for south finish */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_LB, DIR_LB, CHECKPOINT_DIR_S, 1u));
}

/* --- Direction E: fires when facing east (DIR_R, DIR_RT, DIR_RB) --- */

void test_finish_eval_dir_E_valid(void) {
    /* facing east — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, DIR_R, CHECKPOINT_DIR_E, 1u));
}

void test_finish_eval_dir_E_invalid_zero(void) {
    /* facing north (no east component) — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, DIR_T, CHECKPOINT_DIR_E, 1u));
}

void test_finish_eval_dir_E_invalid_west(void) {
    /* facing west — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_L, DIR_L, CHECKPOINT_DIR_E, 1u));
}

/* --- Direction W: fires when facing west (DIR_L, DIR_LT, DIR_LB) --- */

void test_finish_eval_dir_W_valid(void) {
    /* facing west — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_L, DIR_L, CHECKPOINT_DIR_W, 1u));
}

void test_finish_eval_dir_W_invalid_zero(void) {
    /* facing north (no west component) — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, DIR_T, CHECKPOINT_DIR_W, 1u));
}

void test_finish_eval_dir_W_invalid_east(void) {
    /* facing east — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, DIR_R, CHECKPOINT_DIR_W, 1u));
}

void test_cd_stays_in_phase_before_threshold(void) {
    /* CD_FRAMES_NUM - 1 = 59 */
    TEST_ASSERT_EQUAL_UINT8(0u, cd_advance(0u, 59u));
}

void test_cd_advances_at_60_frames(void) {
    /* CD_FRAMES_NUM = 60 */
    TEST_ASSERT_EQUAL_UINT8(1u, cd_advance(0u, 60u));
}

void test_cd_go_stays_before_45(void) {
    /* CD_FRAMES_GO - 1 = 44 */
    TEST_ASSERT_EQUAL_UINT8(3u, cd_advance(3u, 44u));
}

void test_cd_go_advances_at_45_frames(void) {
    /* CD_FRAMES_GO = 45 */
    TEST_ASSERT_EQUAL_UINT8(4u, cd_advance(3u, 45u));
}

/* #628 gave the facing a turn rate; #646 stopped that from costing a lap. Pressing
 * south one frame before the line no longer refuses the crossing: the facing is one
 * notch short, but the notch the car is turning to (DIR_RB) is in the south set, so
 * the lap is credited. This is the driven form of AC1 — real player state, not a
 * hand-built argument list — and it is the test that fails on today's finish_eval. */
void test_finish_gate_credits_a_facing_still_mid_sweep(void) {
    uint8_t i;
    player_init(0u);
    player_set_dir(DIR_R);
    player_apply_physics(J_DOWN, TILE_ROAD);          /* request south, one frame */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u,
                                (uint8_t)player_get_dir(),
                                (uint8_t)player_get_requested_dir(),
                                CHECKPOINT_DIR_S, 1u));

    for (i = 1u; i < (uint8_t)(2u * TURN_PERIOD); i++) {
        player_apply_physics(J_DOWN, TILE_ROAD);      /* R -> RB -> B */
    }
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u,
                                (uint8_t)player_get_dir(),
                                (uint8_t)player_get_requested_dir(),
                                CHECKPOINT_DIR_S, 1u));
}

/* --- #646: a crossing one notch short of the whitelist --- */

/* Correcting onto a south finish straight: facing east, asking for south. The
 * next notch is DIR_RB, which is in the south set, so the lap is credited. */
void test_finish_eval_one_notch_short_is_credited(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, DIR_B, CHECKPOINT_DIR_S, 1u));
}

/* The mirror case, correcting from the west side. */
void test_finish_eval_one_notch_short_from_the_other_side_is_credited(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_L, DIR_B, CHECKPOINT_DIR_S, 1u));
}

/* Two notches short is still refused — the latch is one notch, not a free pass. */
void test_finish_eval_two_notches_short_is_refused(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_RT, DIR_B, CHECKPOINT_DIR_S, 1u));
}

/* R2: facing opposite the finish direction is refused even while pressing toward
 * the line. diff == 4 steps clockwise to DIR_RT, which is not in the south set. */
void test_finish_eval_wrong_way_intent_refused(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, DIR_B, CHECKPOINT_DIR_S, 1u));
}

/* The 180 degree request grants no notch credit: facing east, pressing west, on a
 * south finish. player.c would rotate to DIR_RB, but that is a half-turn, not a
 * correction toward the line, so the gate declines it — see "Why the intent latch". */
void test_finish_eval_half_turn_grants_no_notch(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, DIR_L, CHECKPOINT_DIR_S, 1u));
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_L, DIR_R, CHECKPOINT_DIR_S, 1u));
}

/* The checkpoint gate is untouched by the notch step. */
void test_finish_eval_one_notch_short_still_needs_checkpoints(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, DIR_B, CHECKPOINT_DIR_S, 0u));
}

/* The debounce is untouched by the notch step. */
void test_finish_eval_one_notch_short_still_needs_arming(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 0u, DIR_R, DIR_B, CHECKPOINT_DIR_S, 1u));
}

/* The notch step inside state_playing.c must agree with the facing src/player.c
 * actually rotates to, for all 64 (facing, request) pairs — the half-turn excepted.
 * The oracle is player.c's OBSERVED behaviour, not a retyped copy of the rule: drive
 * the real turn and read player_get_dir(). A retyped copy would stay green if
 * turn_toward_request() changed, which is the divergence this test exists to catch. */
static uint8_t buttons_for_dir(uint8_t d) {
    switch (d) {
        case DIR_T:  return J_UP;
        case DIR_RT: return (uint8_t)(J_UP | J_RIGHT);
        case DIR_R:  return J_RIGHT;
        case DIR_RB: return (uint8_t)(J_DOWN | J_RIGHT);
        case DIR_B:  return J_DOWN;
        case DIR_LB: return (uint8_t)(J_DOWN | J_LEFT);
        case DIR_L:  return J_LEFT;
        default:     return (uint8_t)(J_UP | J_LEFT);   /* DIR_LT */
    }
}

static uint8_t in_south_set(uint8_t d) {
    return (uint8_t)((d == DIR_B || d == DIR_RB || d == DIR_LB) ? 1u : 0u);
}

void test_finish_eval_notch_step_matches_the_facing_player_c_turns_to(void) {
    uint8_t cur, req, i, next, diff, expected;
    for (cur = 0u; cur < 8u; cur++) {
        for (req = 0u; req < 8u; req++) {
            diff = (uint8_t)((uint8_t)(req - cur) & 7u);

            /* Observe the facing player.c reaches after exactly one notch. */
            player_init(0u);
            player_set_dir((player_dir_t)cur);
            for (i = 0u; i < TURN_PERIOD; i++) {
                player_apply_physics(buttons_for_dir(req), TILE_ROAD);
            }
            next = (uint8_t)player_get_dir();

            /* The gate credits the facing, or that observed next notch — except on a
             * half turn (diff == 4), where it deliberately grants no notch credit. */
            expected = (uint8_t)((in_south_set(cur) ||
                                  (diff != 4u && in_south_set(next))) ? 1u : 0u);
            TEST_ASSERT_EQUAL_UINT8(expected,
                finish_eval(TRACK_TYPE_RACE, 1u, cur, req, CHECKPOINT_DIR_S, 1u));
        }
    }
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_finish_eval_race_all_conditions_met);
    RUN_TEST(test_finish_eval_race_missing_checkpoint);
    RUN_TEST(test_finish_eval_race_not_armed);
    RUN_TEST(test_finish_eval_race_wrong_direction);
    RUN_TEST(test_finish_eval_combat_no_checkpoint_needed);
    RUN_TEST(test_finish_eval_combat_not_armed);
    RUN_TEST(test_finish_eval_combat_wrong_direction);
    RUN_TEST(test_finish_eval_dir_N_valid);
    RUN_TEST(test_finish_eval_dir_N_invalid_zero);
    RUN_TEST(test_finish_eval_dir_N_invalid_south);
    RUN_TEST(test_finish_eval_dir_S_valid);
    RUN_TEST(test_finish_eval_dir_S_invalid_zero);
    RUN_TEST(test_finish_eval_dir_S_invalid_north);
    RUN_TEST(test_finish_eval_dir_S_racer_blocked_still_counts);
    RUN_TEST(test_finish_eval_dir_E_valid);
    RUN_TEST(test_finish_eval_dir_E_invalid_zero);
    RUN_TEST(test_finish_eval_dir_E_invalid_west);
    RUN_TEST(test_finish_eval_dir_W_valid);
    RUN_TEST(test_finish_eval_dir_W_invalid_zero);
    RUN_TEST(test_finish_eval_dir_W_invalid_east);
    RUN_TEST(test_cd_stays_in_phase_before_threshold);
    RUN_TEST(test_cd_advances_at_60_frames);
    RUN_TEST(test_cd_go_stays_before_45);
    RUN_TEST(test_cd_go_advances_at_45_frames);
    RUN_TEST(test_finish_gate_credits_a_facing_still_mid_sweep);
    RUN_TEST(test_finish_eval_one_notch_short_is_credited);
    RUN_TEST(test_finish_eval_one_notch_short_from_the_other_side_is_credited);
    RUN_TEST(test_finish_eval_two_notches_short_is_refused);
    RUN_TEST(test_finish_eval_wrong_way_intent_refused);
    RUN_TEST(test_finish_eval_half_turn_grants_no_notch);
    RUN_TEST(test_finish_eval_one_notch_short_still_needs_checkpoints);
    RUN_TEST(test_finish_eval_one_notch_short_still_needs_arming);
    RUN_TEST(test_finish_eval_notch_step_matches_the_facing_player_c_turns_to);
    return UNITY_END();
}
