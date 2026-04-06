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
    loadout_cycle_car(1);   /* 0 -> 1 */
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_car());
    loadout_cycle_armor(1);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_armor());
    loadout_cycle_weapon1(1);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_weapon1());
    loadout_cycle_weapon2(1);
    TEST_ASSERT_EQUAL_UINT8(1u, loadout_get_weapon2());
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
    return UNITY_END();
}
