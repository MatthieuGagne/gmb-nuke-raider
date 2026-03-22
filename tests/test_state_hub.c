#include "unity.h"
#include "state_hub.h"
#include "config.h"
#include "input.h"
#include "music.h"

static void tick(uint8_t btn) {
    prev_input = 0; input = btn;
    frame_ready = 1;           /* prevent VBlank spin from deadlocking host tests */
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

void test_render_wrapped_returns_zero_when_text_fits(void) {
    /* Short text: fits in 5 rows × 12 cols → returns 0 */
    uint8_t resume = render_wrapped("Short text.", 7u, 2u, 12u, 5u, 0u);
    TEST_ASSERT_EQUAL_UINT8(0u, resume);
}

void test_render_wrapped_returns_nonzero_offset_on_overflow(void) {
    /* Text long enough to overflow 5 rows at width 12 → returns non-zero */
    const char *long_text =
        "word1 word2 word3 word4 word5 word6 word7 word8 "
        "word9 word10 word11 word12 word13 word14 word15";
    uint8_t resume = render_wrapped(long_text, 7u, 2u, 12u, 5u, 0u);
    TEST_ASSERT_NOT_EQUAL(0u, resume);
    /* Rendering from resume offset should eventually return 0 */
    {
        uint8_t done = render_wrapped(long_text, 7u, 2u, 12u, 5u, resume);
        TEST_ASSERT_EQUAL_UINT8(0u, done);
    }
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
    RUN_TEST(test_render_wrapped_returns_zero_when_text_fits);
    RUN_TEST(test_render_wrapped_returns_nonzero_offset_on_overflow);
    return UNITY_END();
}
