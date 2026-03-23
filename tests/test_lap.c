#include "unity.h"
#include "../src/lap.h"

void setUp(void)    {}
void tearDown(void) {}

/* After lap_init(3): current=1, total=3 */
void test_lap_init_sets_current_to_one(void) {
    lap_init(3u);
    TEST_ASSERT_EQUAL_UINT8(1u, lap_get_current());
}

void test_lap_init_sets_total(void) {
    lap_init(3u);
    TEST_ASSERT_EQUAL_UINT8(3u, lap_get_total());
}

/* lap_advance on lap 1 of 3: returns 0 (not done), current becomes 2 */
void test_lap_advance_not_done_returns_zero(void) {
    lap_init(3u);
    TEST_ASSERT_EQUAL_UINT8(0u, lap_advance());
}

void test_lap_advance_increments_current(void) {
    lap_init(3u);
    lap_advance();
    TEST_ASSERT_EQUAL_UINT8(2u, lap_get_current());
}

/* Final lap: advance returns 1 (race complete), current stays at total */
void test_lap_advance_final_lap_returns_one(void) {
    lap_init(1u);
    TEST_ASSERT_EQUAL_UINT8(1u, lap_advance());
}

void test_lap_advance_current_caps_at_total(void) {
    lap_init(1u);
    lap_advance();
    TEST_ASSERT_EQUAL_UINT8(1u, lap_get_current());
}

/* Three-lap race full sequence */
void test_lap_three_laps_full_sequence(void) {
    lap_init(3u);
    TEST_ASSERT_EQUAL_UINT8(0u, lap_advance()); /* lap 1 complete: 2/3 */
    TEST_ASSERT_EQUAL_UINT8(2u, lap_get_current());
    TEST_ASSERT_EQUAL_UINT8(0u, lap_advance()); /* lap 2 complete: 3/3 */
    TEST_ASSERT_EQUAL_UINT8(3u, lap_get_current());
    TEST_ASSERT_EQUAL_UINT8(1u, lap_advance()); /* lap 3 complete: race done */
}

/* Reinit resets state */
void test_lap_reinit_resets_state(void) {
    lap_init(5u);
    lap_advance();
    lap_init(3u);
    TEST_ASSERT_EQUAL_UINT8(1u, lap_get_current());
    TEST_ASSERT_EQUAL_UINT8(3u, lap_get_total());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_lap_init_sets_current_to_one);
    RUN_TEST(test_lap_init_sets_total);
    RUN_TEST(test_lap_advance_not_done_returns_zero);
    RUN_TEST(test_lap_advance_increments_current);
    RUN_TEST(test_lap_advance_final_lap_returns_one);
    RUN_TEST(test_lap_advance_current_caps_at_total);
    RUN_TEST(test_lap_three_laps_full_sequence);
    RUN_TEST(test_lap_reinit_resets_state);
    return UNITY_END();
}
