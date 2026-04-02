#include "unity.h"
#include "track.h"        /* TRACK_TYPE_RACE, TRACK_TYPE_COMBAT */
#include "state_playing.h" /* finish_eval */

void setUp(void) {}
void tearDown(void) {}

/* finish_eval(map_type, armed, pvy, cps_cleared) -> 1 = should transition */

/* Race: requires armed + downward velocity + all checkpoints */
void test_finish_eval_race_all_conditions_met(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, 1, 1u));
}

void test_finish_eval_race_missing_checkpoint(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 1, 0u));
}

void test_finish_eval_race_not_armed(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 0u, 1, 1u));
}

void test_finish_eval_race_wrong_direction(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, -1, 1u));
}

/* Combat: requires only armed + downward velocity (no checkpoint gate) */
void test_finish_eval_combat_no_checkpoint_needed(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_COMBAT, 1u, 1, 0u));
}

void test_finish_eval_combat_not_armed(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_COMBAT, 0u, 1, 0u));
}

void test_finish_eval_combat_wrong_direction(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_COMBAT, 1u, -1, 0u));
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
    return UNITY_END();
}
