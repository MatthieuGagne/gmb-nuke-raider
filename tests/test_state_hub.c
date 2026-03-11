#include "unity.h"
#include "state_hub.h"
#include "config.h"
#include "input.h"

static void tick(uint8_t btn) {
    prev_input = 0; input = btn;
    state_hub.update();
    prev_input = input; input = 0;
}

void setUp(void) {
    input = 0; prev_input = 0;
    state_hub.enter();
}
void tearDown(void) {}

void test_enter_clears_hub_entered_flag(void) {
    overmap_hub_entered = 1u;
    state_hub.enter();
    TEST_ASSERT_EQUAL_UINT8(0u, overmap_hub_entered);
}
void test_cursor_starts_at_zero(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, hub_get_cursor());
}
void test_cursor_down_increments(void) {
    tick(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(1u, hub_get_cursor());
}
void test_cursor_up_decrements(void) {
    tick(J_DOWN);
    tick(J_UP);
    TEST_ASSERT_EQUAL_UINT8(0u, hub_get_cursor());
}
void test_cursor_up_clamped_at_zero(void) {
    tick(J_UP);
    TEST_ASSERT_EQUAL_UINT8(0u, hub_get_cursor());
}
void test_cursor_down_clamped_at_leave(void) {
    uint8_t i;
    for (i = 0u; i < 10u; i++) tick(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(MAX_HUB_NPCS, hub_get_cursor()); /* Leave = index 3 */
}
void test_a_on_npc_enters_dialog_substate(void) {
    tick(J_A); /* cursor=0, Mechanic */
    TEST_ASSERT_EQUAL_UINT8(1u, hub_get_sub_state());
}
void test_a_on_leave_does_not_enter_dialog(void) {
    uint8_t i;
    for (i = 0u; i < MAX_HUB_NPCS; i++) tick(J_DOWN);
    tick(J_A);
    TEST_ASSERT_NOT_EQUAL(1u, hub_get_sub_state());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_enter_clears_hub_entered_flag);
    RUN_TEST(test_cursor_starts_at_zero);
    RUN_TEST(test_cursor_down_increments);
    RUN_TEST(test_cursor_up_decrements);
    RUN_TEST(test_cursor_up_clamped_at_zero);
    RUN_TEST(test_cursor_down_clamped_at_leave);
    RUN_TEST(test_a_on_npc_enters_dialog_substate);
    RUN_TEST(test_a_on_leave_does_not_enter_dialog);
    return UNITY_END();
}
