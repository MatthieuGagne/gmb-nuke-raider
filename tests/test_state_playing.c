#include "unity.h"
#include "track.h"         /* TRACK_TYPE_RACE, TRACK_TYPE_COMBAT, CHECKPOINT_DIR_* via checkpoint.h */
#include "state_playing.h" /* finish_eval */

void setUp(void) {}
void tearDown(void) {}

/* finish_eval(map_type, armed, pvx, pvy, finish_dir, cps_cleared) -> 1 = transition */

/* --- Existing race/combat gate tests (updated to new signature, dir=S) --- */

void test_finish_eval_race_all_conditions_met(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, 0, 1, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_race_missing_checkpoint(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 0, 1, CHECKPOINT_DIR_S, 0u));
}

void test_finish_eval_race_not_armed(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 0u, 0, 1, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_race_wrong_direction(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 0, -1, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_combat_no_checkpoint_needed(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_COMBAT, 1u, 0, 1, CHECKPOINT_DIR_S, 0u));
}

void test_finish_eval_combat_not_armed(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_COMBAT, 0u, 0, 1, CHECKPOINT_DIR_S, 0u));
}

void test_finish_eval_combat_wrong_direction(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_COMBAT, 1u, 0, -1, CHECKPOINT_DIR_S, 0u));
}

/* --- Direction N: fires when vy < 0 --- */

void test_finish_eval_dir_N_valid(void) {
    /* vy=-1: moving north — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, 0, -1, CHECKPOINT_DIR_N, 1u));
}

void test_finish_eval_dir_N_invalid_zero(void) {
    /* vy=0: stationary — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 0, 0, CHECKPOINT_DIR_N, 1u));
}

void test_finish_eval_dir_N_invalid_south(void) {
    /* vy=1: moving south — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 0, 1, CHECKPOINT_DIR_N, 1u));
}

/* --- Direction S: fires when vy > 0 --- */

void test_finish_eval_dir_S_valid(void) {
    /* vy=1: moving south — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, 0, 1, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_dir_S_invalid_zero(void) {
    /* vy=0: stationary — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 0, 0, CHECKPOINT_DIR_S, 1u));
}

void test_finish_eval_dir_S_invalid_north(void) {
    /* vy=-1: moving north — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 0, -1, CHECKPOINT_DIR_S, 1u));
}

/* --- Direction E: fires when vx > 0 --- */

void test_finish_eval_dir_E_valid(void) {
    /* vx=1: moving east — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, 1, 0, CHECKPOINT_DIR_E, 1u));
}

void test_finish_eval_dir_E_invalid_zero(void) {
    /* vx=0: stationary — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 0, 0, CHECKPOINT_DIR_E, 1u));
}

void test_finish_eval_dir_E_invalid_west(void) {
    /* vx=-1: moving west — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, -1, 0, CHECKPOINT_DIR_E, 1u));
}

/* --- Direction W: fires when vx < 0 --- */

void test_finish_eval_dir_W_valid(void) {
    /* vx=-1: moving west — should trigger */
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, -1, 0, CHECKPOINT_DIR_W, 1u));
}

void test_finish_eval_dir_W_invalid_zero(void) {
    /* vx=0: stationary — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 0, 0, CHECKPOINT_DIR_W, 1u));
}

void test_finish_eval_dir_W_invalid_east(void) {
    /* vx=1: moving east — should NOT trigger */
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 1, 0, CHECKPOINT_DIR_W, 1u));
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
    RUN_TEST(test_finish_eval_dir_E_valid);
    RUN_TEST(test_finish_eval_dir_E_invalid_zero);
    RUN_TEST(test_finish_eval_dir_E_invalid_west);
    RUN_TEST(test_finish_eval_dir_W_valid);
    RUN_TEST(test_finish_eval_dir_W_invalid_zero);
    RUN_TEST(test_finish_eval_dir_W_invalid_east);
    return UNITY_END();
}
