/* tests/test_loadout.c */
#include "unity.h"
#include "loadout.h"

void setUp(void) {}
void tearDown(void) {}

void test_loadout_init_sets_defaults(void) {
    loadout_init();
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_get_car());
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_get_armor());
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_get_weapon1());
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_get_weapon2());
}

void test_loadout_set_and_get_car(void) {
    loadout_init();
    loadout_set_car(1u);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_car());
}

void test_loadout_set_and_get_armor(void) {
    loadout_init();
    loadout_set_armor(1u);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_armor());
}

void test_loadout_set_and_get_weapon1(void) {
    loadout_init();
    loadout_set_weapon1(1u);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_weapon1());
}

void test_loadout_set_and_get_weapon2(void) {
    loadout_init();
    loadout_set_weapon2(1u);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_weapon2());
}

void test_loadout_persists_across_calls(void) {
    loadout_init();
    loadout_set_car(1u);
    loadout_set_armor(1u);
    loadout_set_weapon2(1u);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_car());
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_armor());
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_get_weapon1());  /* untouched */
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_weapon2());
}

void test_loadout_cycling_wraps_right(void) {
    /* Right on index 1 (last) -> wraps to 0 */
    loadout_init();
    loadout_set_car(1u);
    loadout_cycle_car(1);   /* +1 -> wraps to 0 */
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_get_car());
}

void test_loadout_cycling_wraps_left(void) {
    /* Left on index 0 (first) -> wraps to 1 */
    loadout_init();
    loadout_set_car(0u);
    loadout_cycle_car(-1);  /* -1 -> wraps to 1 */
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_car());
}

void test_loadout_cycling_normal(void) {
    loadout_init();
    loadout_cycle_car(1);   /* 0 -> 1 (CAR never gated) */
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_car());
    loadout_unlock_option(LOADOUT_FIELD_ARMOR);
    loadout_cycle_armor(1);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_armor());
    loadout_unlock_option(LOADOUT_FIELD_WEAPON1);
    loadout_cycle_weapon1(1);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_weapon1());
    loadout_unlock_option(LOADOUT_FIELD_WEAPON2);
    loadout_cycle_weapon2(1);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_weapon2());
}

void test_loadout_init_locks_tier1_except_car(void) {
    loadout_init();
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_is_option_unlocked(LOADOUT_FIELD_ARMOR, 0u));
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_is_option_unlocked(LOADOUT_FIELD_ARMOR, 1u));
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_is_option_unlocked(LOADOUT_FIELD_WEAPON1, 1u));
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_is_option_unlocked(LOADOUT_FIELD_WEAPON2, 1u));
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_is_option_unlocked(LOADOUT_FIELD_CAR, 1u));
}

void test_loadout_unlock_option_sets_bit(void) {
    loadout_init();
    loadout_unlock_option(LOADOUT_FIELD_ARMOR);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_is_option_unlocked(LOADOUT_FIELD_ARMOR, 1u));
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_is_option_unlocked(LOADOUT_FIELD_WEAPON1, 1u));
}

void test_loadout_cycle_skips_locked(void) {
    loadout_init();
    loadout_cycle_armor(1);
    TEST_ASSERT_EQUAL_UINT8(0u, loadout_get_armor());
}

void test_loadout_cycle_reaches_unlocked(void) {
    loadout_init();
    loadout_unlock_option(LOADOUT_FIELD_ARMOR);
    loadout_cycle_armor(1);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_armor());
}

void test_loadout_car_cycles_without_unlock(void) {
    loadout_init();
    loadout_cycle_car(1);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_car());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_loadout_init_sets_defaults);
    RUN_TEST(test_loadout_set_and_get_car);
    RUN_TEST(test_loadout_set_and_get_armor);
    RUN_TEST(test_loadout_set_and_get_weapon1);
    RUN_TEST(test_loadout_set_and_get_weapon2);
    RUN_TEST(test_loadout_persists_across_calls);
    RUN_TEST(test_loadout_cycling_wraps_right);
    RUN_TEST(test_loadout_cycling_wraps_left);
    RUN_TEST(test_loadout_cycling_normal);
    RUN_TEST(test_loadout_init_locks_tier1_except_car);
    RUN_TEST(test_loadout_unlock_option_sets_bit);
    RUN_TEST(test_loadout_cycle_skips_locked);
    RUN_TEST(test_loadout_cycle_reaches_unlocked);
    RUN_TEST(test_loadout_car_cycles_without_unlock);
    return UNITY_END();
}
