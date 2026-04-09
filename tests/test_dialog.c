#include "unity.h"
#include "dialog.h"
#include <string.h>

/* --- Inline test dialog data (named static arrays per SDCC rules) --- */

static const char tn0_text[] = "Hello traveler!";
static const char tn1_text[] = "What do you want?";
static const char tn2_text[] = "Good trade!";
static const char tn3_text[] = "Prepare to die!";
static const char tn1_c0[]   = "Trade";
static const char tn1_c1[]   = "Fight";
static const char test_npc_name[] = "VENDOR";

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

static const NpcDialog test_dialog_data = { test_nodes, 4, test_npc_name };

/* Helper: populate WRAM caches directly from a test NpcDialog + node_idx.
 * Replaces loader_dialog_cache_node for host tests (no ROM bank switch needed). */
static void test_cache_node(const NpcDialog *dlg, uint8_t node_idx) {
    const DialogNode *node = &dlg->nodes[node_idx];
    uint8_t i;
    uint8_t k;
    const char *src;

    src = dlg->name ? dlg->name : "";
    for (k = 0u; src[k] && k < DIALOG_NAME_BUF_LEN - 1u; k++)
        dialog_name_cache[k] = src[k];
    dialog_name_cache[k] = '\0';

    src = node->text ? node->text : "";
    for (k = 0u; src[k] && k < DIALOG_TEXT_BUF_LEN - 1u; k++)
        dialog_text_cache[k] = src[k];
    dialog_text_cache[k] = '\0';

    dialog_num_choices_cache = node->num_choices;
    for (i = 0u; i < 3u; i++)
        dialog_next_cache[i] = node->next[i];

    for (i = 0u; i < 3u; i++) {
        if (node->choices[i]) {
            src = node->choices[i];
            for (k = 0u; src[k] && k < DIALOG_CHOICE_BUF_LEN - 1u; k++)
                dialog_choice_cache[i][k] = src[k];
            dialog_choice_cache[i][k] = '\0';
        } else {
            dialog_choice_cache[i][0] = '\0';
        }
    }
}

/* Helper: advance dialog, re-populating cache from test data afterward.
 * In production, dialog_advance calls loader_dialog_cache_node (reads npc_dialogs ROM).
 * In host tests, loader_dialog_cache_node reads npc_dialogs[0] from dialog_data.c,
 * not our test nodes. We save next_idx before the call, then re-cache from test data. */
static uint8_t test_dialog_advance(const NpcDialog *dlg, uint8_t choice_idx) {
    uint8_t next_idx;
    uint8_t more;

    /* Capture next_idx from cache before dialog_advance overwrites it */
    if (dialog_num_choices_cache == 0u)
        next_idx = dialog_next_cache[0];
    else
        next_idx = dialog_next_cache[choice_idx];

    more = dialog_advance(choice_idx);

    /* Re-populate test cache if there is a next node */
    if (more && next_idx != DIALOG_END) {
        test_cache_node(dlg, next_idx);
    }
    return more;
}

/* --- setUp / tearDown ---------------------------------------------------- */

void setUp(void) {
    dialog_init();
    test_cache_node(&test_dialog_data, 0u);
    dialog_start(0u);
}
void tearDown(void) {}

/* --- Test: linear advance ----------------------------------------------- */

void test_dialog_get_text_returns_first_node(void) {
    TEST_ASSERT_EQUAL_STRING("Hello traveler!", dialog_get_text());
}

void test_dialog_first_node_is_narration(void) {
    TEST_ASSERT_EQUAL_UINT8(0, dialog_get_num_choices());
}

void test_dialog_advance_narration_moves_to_next(void) {
    test_dialog_advance(&test_dialog_data, 0u);
    TEST_ASSERT_EQUAL_STRING("What do you want?", dialog_get_text());
}

/* --- Test: branching choice --------------------------------------------- */

void test_dialog_choice_node_has_two_choices(void) {
    test_dialog_advance(&test_dialog_data, 0u);
    TEST_ASSERT_EQUAL_UINT8(2, dialog_get_num_choices());
}

void test_dialog_get_choice_returns_label(void) {
    test_dialog_advance(&test_dialog_data, 0u);
    TEST_ASSERT_EQUAL_STRING("Trade", dialog_get_choice(0));
    TEST_ASSERT_EQUAL_STRING("Fight", dialog_get_choice(1));
}

void test_dialog_branch_choice_0_leads_to_trade_node(void) {
    test_dialog_advance(&test_dialog_data, 0u);
    test_dialog_advance(&test_dialog_data, 0u);
    TEST_ASSERT_EQUAL_STRING("Good trade!", dialog_get_text());
}

void test_dialog_branch_choice_1_leads_to_fight_node(void) {
    test_dialog_advance(&test_dialog_data, 0u);
    test_dialog_advance(&test_dialog_data, 1u);
    TEST_ASSERT_EQUAL_STRING("Prepare to die!", dialog_get_text());
}

/* --- Test: conversation end --------------------------------------------- */

void test_dialog_advance_returns_0_at_end(void) {
    uint8_t result;
    test_dialog_advance(&test_dialog_data, 0u);
    test_dialog_advance(&test_dialog_data, 0u);
    result = test_dialog_advance(&test_dialog_data, 0u);
    TEST_ASSERT_EQUAL_UINT8(0, result);
}

void test_dialog_advance_returns_1_while_ongoing(void) {
    uint8_t result;
    result = test_dialog_advance(&test_dialog_data, 0u);
    TEST_ASSERT_EQUAL_UINT8(1, result);
}

void test_dialog_end_resets_current_node_to_0(void) {
    test_dialog_advance(&test_dialog_data, 0u);
    test_dialog_advance(&test_dialog_data, 0u);
    test_dialog_advance(&test_dialog_data, 0u); /* END */
    /* Restart: cache node 0 again and call dialog_start */
    test_cache_node(&test_dialog_data, 0u);
    dialog_start(0u);
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

void test_dialog_get_name_returns_correct_name(void) {
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
