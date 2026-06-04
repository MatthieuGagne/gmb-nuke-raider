#include "unity.h"
#include "track.h"         /* TRACK_TYPE_RACE, TRACK_TYPE_COMBAT, CHECKPOINT_DIR_* via checkpoint.h */
#include "state_playing.h" /* finish_eval */

void setUp(void) {}
void tearDown(void) {}

/* finish_eval(map_type, armed, pdir, finish_dir, cps_cleared) -> 1 = transition */

/* --- Race/combat gate tests (finish direction = S) --- */

void test_finish_eval_race_all_conditions_met(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_B, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_race_missing_checkpoint(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_B, CHECKPOINT_DIR_S, 0u));
}

void test_finish_eval_race_not_armed(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 0u, DIR_B, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_race_wrong_direction(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_combat_no_checkpoint_needed(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_COMBAT, 1u, DIR_B, CHECKPOINT_DIR_S, 0u));
}

void test_finish_eval_combat_not_armed(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_COMBAT, 0u, DIR_B, CHECKPOINT_DIR_S, 0u));
}

void test_finish_eval_combat_wrong_direction(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_COMBAT, 1u, DIR_T, CHECKPOINT_DIR_S, 0u));
}

/* --- Direction N: fires when facing north (DIR_T, DIR_RT, DIR_LT) --- */

void test_finish_eval_dir_N_valid(void) {
    /* facing north — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, CHECKPOINT_DIR_N, 1u));
}

void test_finish_eval_dir_N_invalid_zero(void) {
    /* facing east (no north component) — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, CHECKPOINT_DIR_N, 1u));
}

void test_finish_eval_dir_N_invalid_south(void) {
    /* facing south — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_B, CHECKPOINT_DIR_N, 1u));
}

/* --- Direction S: fires when facing south (DIR_B, DIR_RB, DIR_LB) --- */

void test_finish_eval_dir_S_valid(void) {
    /* facing south — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_B, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_dir_S_invalid_zero(void) {
    /* facing east (no south component) — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_dir_S_invalid_north(void) {
    /* facing north — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_dir_S_racer_blocked_still_counts(void) {
    /* Regression #382: diagonal SW approach still counts for south finish */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_LB, CHECKPOINT_DIR_S, 1u));
}

/* --- Direction E: fires when facing east (DIR_R, DIR_RT, DIR_RB) --- */

void test_finish_eval_dir_E_valid(void) {
    /* facing east — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, CHECKPOINT_DIR_E, 1u));
}

void test_finish_eval_dir_E_invalid_zero(void) {
    /* facing north (no east component) — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, CHECKPOINT_DIR_E, 1u));
}

void test_finish_eval_dir_E_invalid_west(void) {
    /* facing west — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_L, CHECKPOINT_DIR_E, 1u));
}

/* --- Direction W: fires when facing west (DIR_L, DIR_LT, DIR_LB) --- */

void test_finish_eval_dir_W_valid(void) {
    /* facing west — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_L, CHECKPOINT_DIR_W, 1u));
}

void test_finish_eval_dir_W_invalid_zero(void) {
    /* facing north (no west component) — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_T, CHECKPOINT_DIR_W, 1u));
}

void test_finish_eval_dir_W_invalid_east(void) {
    /* facing east — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, DIR_R, CHECKPOINT_DIR_W, 1u));
}

/* AC7: pos_from_dir covers all 4 directions, both outcomes each.
 * Semantics: CHECKPOINT_DIR_N = going north → lower py = further ahead.
 *            CHECKPOINT_DIR_S = going south → higher py = further ahead.
 *            CHECKPOINT_DIR_E = going east  → higher px = further ahead.
 *            CHECKPOINT_DIR_W = going west  → lower px  = further ahead.
 * Returns 1 = player ahead, 2 = racer ahead. */
void test_pos_from_dir_N_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_N, 0,  50, 0, 100));
}
void test_pos_from_dir_N_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_N, 0, 100, 0,  50));
}
void test_pos_from_dir_S_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_S, 0, 100, 0,  50));
}
void test_pos_from_dir_S_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_S, 0,  50, 0, 100));
}
void test_pos_from_dir_E_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_E, 100, 0,  50, 0));
}
void test_pos_from_dir_E_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_E,  50, 0, 100, 0));
}
void test_pos_from_dir_W_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_W,  50, 0, 100, 0));
}
void test_pos_from_dir_W_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_W, 100, 0,  50, 0));
}

/* pos_from_manhattan: smaller Manhattan distance to checkpoint center = ahead (P1).
 * Tie (equal distance) favors player → returns 1. */
void test_pos_from_manhattan_player_closer(void) {
    CheckpointDef cp = {100, 100, 20, 20, 0, CHECKPOINT_DIR_N};
    /* center=(110,110). player dist=4, racer dist=40 */
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(112, 112, 90, 90, &cp));
}
void test_pos_from_manhattan_racer_closer(void) {
    CheckpointDef cp = {100, 100, 20, 20, 0, CHECKPOINT_DIR_N};
    /* center=(110,110). player dist=40, racer dist=4 */
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_manhattan(90, 90, 112, 112, &cp));
}
void test_pos_from_manhattan_equal_distance_favors_player(void) {
    CheckpointDef cp = {100, 100, 20, 20, 0, CHECKPOINT_DIR_N};
    /* center=(110,110). player dist=10, racer dist=10 */
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(120, 110, 110, 120, &cp));
}
void test_pos_from_manhattan_nonsquare_checkpoint(void) {
    CheckpointDef cp = {0, 0, 40, 10, 0, CHECKPOINT_DIR_E};
    /* center=(20,5). player dist=1, racer dist=20 */
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(21, 5, 0, 5, &cp));
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
    RUN_TEST(test_pos_from_dir_N_player_ahead);
    RUN_TEST(test_pos_from_dir_N_racer_ahead);
    RUN_TEST(test_pos_from_dir_S_player_ahead);
    RUN_TEST(test_pos_from_dir_S_racer_ahead);
    RUN_TEST(test_pos_from_dir_E_player_ahead);
    RUN_TEST(test_pos_from_dir_E_racer_ahead);
    RUN_TEST(test_pos_from_dir_W_player_ahead);
    RUN_TEST(test_pos_from_dir_W_racer_ahead);
    RUN_TEST(test_pos_from_manhattan_player_closer);
    RUN_TEST(test_pos_from_manhattan_racer_closer);
    RUN_TEST(test_pos_from_manhattan_equal_distance_favors_player);
    RUN_TEST(test_pos_from_manhattan_nonsquare_checkpoint);
    return UNITY_END();
}
