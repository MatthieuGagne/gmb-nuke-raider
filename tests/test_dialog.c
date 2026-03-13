#include "unity.h"
#include "dialog.h"

/* --- Inline test dialog data (ROM-side, named static arrays per SDCC rules) --- */

static const char tn0_text[] = "Hello traveler!";
static const char tn1_text[] = "What do you want?";
static const char tn2_text[] = "Good trade!";
static const char tn3_text[] = "Prepare to die!";
static const char tn1_c0[]   = "Trade";
static const char tn1_c1[]   = "Fight";

/*
 * Graph:
 *   node 0 (narration)  -> node 1
 *   node 1 (2 choices)  -> node 2 (Trade) or node 3 (Fight)
 *   node 2 (narration)  -> END
 *   node 3 (narration)  -> END
 */
static const DialogNode test_nodes[] = {
    { tn0_text, 0, {NULL,   NULL,   NULL}, {1,           0xFFu, 0xFFu} },
    { tn1_text, 2, {tn1_c0, tn1_c1, NULL}, {2,           3,     0xFFu} },
    { tn2_text, 0, {NULL,   NULL,   NULL}, {DIALOG_END,  0xFFu, 0xFFu} },
    { tn3_text, 0, {NULL,   NULL,   NULL}, {DIALOG_END,  0xFFu, 0xFFu} },
};
static const NpcDialog test_dialog = { test_nodes, 4 };

/* --- setUp / tearDown ---------------------------------------------------- */

void setUp(void)    { dialog_init(); }
void tearDown(void) {}

/* --- Test: linear advance ----------------------------------------------- */

void test_dialog_get_text_returns_first_node(void) {
    dialog_start(0, &test_dialog);
    TEST_ASSERT_EQUAL_STRING("Hello traveler!", dialog_get_text());
}

void test_dialog_first_node_is_narration(void) {
    dialog_start(0, &test_dialog);
    TEST_ASSERT_EQUAL_UINT8(0, dialog_get_num_choices());
}

void test_dialog_advance_narration_moves_to_next(void) {
    dialog_start(0, &test_dialog);
    dialog_advance(0);
    TEST_ASSERT_EQUAL_STRING("What do you want?", dialog_get_text());
}

/* --- Test: branching choice --------------------------------------------- */

void test_dialog_choice_node_has_two_choices(void) {
    dialog_start(0, &test_dialog);
    dialog_advance(0);
    TEST_ASSERT_EQUAL_UINT8(2, dialog_get_num_choices());
}

void test_dialog_get_choice_returns_label(void) {
    dialog_start(0, &test_dialog);
    dialog_advance(0);
    TEST_ASSERT_EQUAL_STRING("Trade", dialog_get_choice(0));
    TEST_ASSERT_EQUAL_STRING("Fight", dialog_get_choice(1));
}

void test_dialog_branch_choice_0_leads_to_trade_node(void) {
    dialog_start(0, &test_dialog);
    dialog_advance(0);
    dialog_advance(0);
    TEST_ASSERT_EQUAL_STRING("Good trade!", dialog_get_text());
}

void test_dialog_branch_choice_1_leads_to_fight_node(void) {
    dialog_start(0, &test_dialog);
    dialog_advance(0);
    dialog_advance(1);
    TEST_ASSERT_EQUAL_STRING("Prepare to die!", dialog_get_text());
}

/* --- Test: conversation end --------------------------------------------- */

void test_dialog_advance_returns_0_at_end(void) {
    uint8_t result;
    dialog_start(0, &test_dialog);
    dialog_advance(0);
    dialog_advance(0);
    result = dialog_advance(0);
    TEST_ASSERT_EQUAL_UINT8(0, result);
}

void test_dialog_advance_returns_1_while_ongoing(void) {
    uint8_t result;
    dialog_start(0, &test_dialog);
    result = dialog_advance(0);
    TEST_ASSERT_EQUAL_UINT8(1, result);
}

void test_dialog_end_resets_current_node_to_0(void) {
    dialog_start(0, &test_dialog);
    dialog_advance(0);
    dialog_advance(0);
    dialog_advance(0); /* END */
    dialog_start(0, &test_dialog);
    TEST_ASSERT_EQUAL_STRING("Hello traveler!", dialog_get_text());
}

/* --- Test: flag round-trip ---------------------------------------------- */

void test_dialog_flag_starts_clear(void) {
    TEST_ASSERT_EQUAL_UINT8(0, dialog_get_flag(0, 0));
}

void test_dialog_set_flag_makes_get_flag_true(void) {
    dialog_set_flag(0, 3);
    TEST_ASSERT_EQUAL_UINT8(1, dialog_get_flag(0, 3));
}

void test_dialog_flag_is_per_npc(void) {
    dialog_set_flag(0, 2);
    TEST_ASSERT_EQUAL_UINT8(0, dialog_get_flag(1, 2));
}

void test_dialog_multiple_flags_independent(void) {
    dialog_set_flag(0, 0);
    dialog_set_flag(0, 7);
    TEST_ASSERT_EQUAL_UINT8(1, dialog_get_flag(0, 0));
    TEST_ASSERT_EQUAL_UINT8(0, dialog_get_flag(0, 1));
    TEST_ASSERT_EQUAL_UINT8(1, dialog_get_flag(0, 7));
}

/* --- Test: NPC name ---------------------------------------------------- */

static const NpcDialog named_dialog = {
    test_nodes, 4, "VENDOR"
};

void test_dialog_get_name_returns_correct_name(void) {
    dialog_start(0, &named_dialog);
    TEST_ASSERT_EQUAL_STRING("VENDOR", dialog_get_name());
}

/* --- runner ------------------------------------------------------------- */

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_dialog_get_text_returns_first_node);
    RUN_TEST(test_dialog_first_node_is_narration);
    RUN_TEST(test_dialog_advance_narration_moves_to_next);
    RUN_TEST(test_dialog_choice_node_has_two_choices);
    RUN_TEST(test_dialog_get_choice_returns_label);
    RUN_TEST(test_dialog_branch_choice_0_leads_to_trade_node);
    RUN_TEST(test_dialog_branch_choice_1_leads_to_fight_node);
    RUN_TEST(test_dialog_advance_returns_0_at_end);
    RUN_TEST(test_dialog_advance_returns_1_while_ongoing);
    RUN_TEST(test_dialog_end_resets_current_node_to_0);
    RUN_TEST(test_dialog_flag_starts_clear);
    RUN_TEST(test_dialog_set_flag_makes_get_flag_true);
    RUN_TEST(test_dialog_flag_is_per_npc);
    RUN_TEST(test_dialog_multiple_flags_independent);
    RUN_TEST(test_dialog_get_name_returns_correct_name);
    return UNITY_END();
}
