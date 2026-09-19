#include "unity.h"
#include "state_hub.h"
#include "loader.h"
#include "config.h"
#include "input.h"
#include "music.h"
#include "economy.h"
#include "loadout.h"

static void tick(uint8_t btn) {
    prev_input = 0; input = btn;
    frame_ready = 1;           /* prevent VBlank spin from deadlocking host tests */
    state_hub.update();
    prev_input = input; input = 0;
}

void setUp(void) {
    loader_reset_bitmap_for_test(); /* clear loader state so enter() can call loader_load_state() */
    input = 0; prev_input = 0;
    state_hub.enter();
}
void tearDown(void) {}

void test_enter_clears_hub_entered_flag(void) {
    overmap_hub_entered = 1u;
    state_hub.exit();
    loader_reset_bitmap_for_test();
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

void test_dialog_advances_through_pages_and_back_to_menu(void) {
    /* NPC 0 (mechanic): node 0 narration overflows the width-12 box to 2 pages;
     * node 1 next = {2, 3, DIALOG_END}; node 3 choices = {DIALOG_SHOP, DIALOG_END}. */
    tick(J_A);                       /* enter DIALOG sub-state (1), node 0 page 1 */
    TEST_ASSERT_EQUAL_UINT8(1u, hub_get_sub_state());
    tick(J_A);                       /* node 0 page 2 ("Caps.") */
    TEST_ASSERT_EQUAL_UINT8(1u, hub_get_sub_state());
    tick(J_A);                       /* node 0 -> node 1 */
    TEST_ASSERT_EQUAL_UINT8(1u, hub_get_sub_state());   /* still talking */
    tick(J_DOWN);                    /* cursor to choice 1 */
    tick(J_A);                       /* node 1 choice 1 -> node 3 */
    tick(J_DOWN);                    /* cursor to choice 1 = DIALOG_END */
    tick(J_A);                       /* advance to END -> back to menu */
    TEST_ASSERT_EQUAL_UINT8(0u, hub_get_sub_state());
}

void test_dialog_choice_cursor_moves_and_clamps(void) {
    tick(J_A);                       /* node 0 page 1 */
    tick(J_A);                       /* node 0 page 2 */
    tick(J_A);                       /* node 1: 3 choices */
    tick(J_UP);                      /* cursor already 0: guard refuses, no move */
    tick(J_DOWN);                    /* cursor 1 */
    tick(J_DOWN);                    /* cursor 2 */
    tick(J_DOWN);                    /* clamped at num_choices-1 */
    TEST_ASSERT_EQUAL_UINT8(1u, hub_get_sub_state());   /* no crash, still in dialog */
}

void test_dialog_shop_choice_enters_shop(void) {
    tick(J_A);                       /* node 0 page 1 */
    tick(J_A);                       /* node 0 page 2 */
    tick(J_A);                       /* node 1 */
    tick(J_DOWN);                    /* choice 1 */
    tick(J_A);                       /* -> node 3 */
    tick(J_A);                       /* choice 0 = DIALOG_SHOP -> hub_enter_shop */
    TEST_ASSERT_EQUAL_UINT8(2u, hub_get_sub_state());
}

void test_shop_buys_when_scrap_sufficient(void) {
    economy_init();
    loadout_init();
    tick(J_A); tick(J_A); tick(J_A); /* node 0 (2 pages) -> node 1 */
    tick(J_DOWN); tick(J_A);         /* -> node 3 */
    tick(J_A);                       /* -> SHOP */
    TEST_ASSERT_EQUAL_UINT8(2u, hub_get_sub_state());
    economy_add_scrap(999u);
    tick(J_A);                       /* buy: spend + unlock */
    TEST_ASSERT_TRUE(economy_get_scrap() < 999u);
}

void test_shop_ignores_purchase_without_funds(void) {
    economy_init();
    loadout_init();
    tick(J_A); tick(J_A); tick(J_A);
    tick(J_DOWN); tick(J_A);
    tick(J_A);                       /* -> SHOP */
    tick(J_A);                       /* no scrap: no-op */
    TEST_ASSERT_EQUAL_UINT8(0u, economy_get_scrap());
    TEST_ASSERT_EQUAL_UINT8(2u, hub_get_sub_state());
}

void test_shop_b_returns_to_menu(void) {
    tick(J_A); tick(J_A); tick(J_A);
    tick(J_DOWN); tick(J_A);
    tick(J_A);                       /* -> SHOP */
    tick(J_B);
    TEST_ASSERT_EQUAL_UINT8(0u, hub_get_sub_state());
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

void test_hub_clear_does_not_write_rows_18_to_31(void) {
    /* After hub enter(), set_bkg_tile_xy must never touch rows 18-31.
     * If cls() is still present, it writes rows 0-31 via GBDK internals —
     * but in the host mock, cls() is a no-op, so this test catches the
     * case where our new clear_visible_rows() accidentally clears beyond row 17. */
    state_hub.exit();
    loader_reset_bitmap_for_test();
    mock_vram_clear();
    state_hub.enter();
    TEST_ASSERT_LESS_OR_EQUAL_UINT8(17u, mock_set_bkg_tile_xy_max_row);
}

void test_hub_cursor_move_does_not_trigger_full_clear(void) {
    /* A cursor keypress must NOT call set_bkg_tile_xy (dirty update only).
     * Before the fix, hub_render_menu() was called on every keypress,
     * which would invoke clear_visible_rows() and increment the count. */
    state_hub.exit();
    loader_reset_bitmap_for_test();
    state_hub.enter();
    mock_set_bkg_tile_xy_reset();   /* reset counter AFTER enter (enter legitimately clears) */
    tick(J_DOWN);                   /* move cursor — should only write 2 console tiles */
    TEST_ASSERT_EQUAL_INT(0, mock_set_bkg_tile_xy_call_count);
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
    RUN_TEST(test_dialog_advances_through_pages_and_back_to_menu);
    RUN_TEST(test_dialog_choice_cursor_moves_and_clamps);
    RUN_TEST(test_dialog_shop_choice_enters_shop);
    RUN_TEST(test_shop_buys_when_scrap_sufficient);
    RUN_TEST(test_shop_ignores_purchase_without_funds);
    RUN_TEST(test_shop_b_returns_to_menu);
    RUN_TEST(test_render_wrapped_returns_zero_when_text_fits);
    RUN_TEST(test_render_wrapped_returns_nonzero_offset_on_overflow);
    RUN_TEST(test_hub_clear_does_not_write_rows_18_to_31);
    RUN_TEST(test_hub_cursor_move_does_not_trigger_full_clear);
    return UNITY_END();
}
