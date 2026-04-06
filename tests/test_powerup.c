#include "unity.h"
#include "powerup.h"
#include "config.h"

void setUp(void)    { powerup_init_empty(); }
void tearDown(void) {}

void test_powerup_pool_empty_after_init_empty(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, powerup_count_active());
}

void test_powerup_type_constant_defined(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, POWERUP_TYPE_HEAL);
}

void test_powerup_spawn_and_active(void) {
    powerup_test_spawn(5u, 5u, POWERUP_TYPE_HEAL);
    TEST_ASSERT_EQUAL_UINT8(1u, powerup_count_active());
}

void test_powerup_no_collect_when_player_elsewhere(void) {
    powerup_test_spawn(5u, 5u, POWERUP_TYPE_HEAL);
    powerup_update(10u, 10u);
    TEST_ASSERT_EQUAL_UINT8(1u, powerup_count_active());
}

void test_powerup_collect_deactivates(void) {
    powerup_test_spawn(5u, 5u, POWERUP_TYPE_HEAL);
    powerup_update(5u, 5u);  /* player at same tile → collect */
    TEST_ASSERT_EQUAL_UINT8(0u, powerup_count_active());
}

void test_powerup_collect_is_one_shot(void) {
    powerup_test_spawn(5u, 5u, POWERUP_TYPE_HEAL);
    powerup_update(5u, 5u);  /* collect */
    powerup_update(5u, 5u);  /* second pass — no active powerup */
    TEST_ASSERT_EQUAL_UINT8(0u, powerup_count_active());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_powerup_pool_empty_after_init_empty);
    RUN_TEST(test_powerup_type_constant_defined);
    RUN_TEST(test_powerup_spawn_and_active);
    RUN_TEST(test_powerup_no_collect_when_player_elsewhere);
    RUN_TEST(test_powerup_collect_deactivates);
    RUN_TEST(test_powerup_collect_is_one_shot);
    return UNITY_END();
}
