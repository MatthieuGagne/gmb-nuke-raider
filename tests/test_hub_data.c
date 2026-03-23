#include "unity.h"
#include "hub_data.h"

void setUp(void)    {}
void tearDown(void) {}

void test_hub_table_count(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, hub_table_count);
}
void test_hub_table_has_rust_town(void) {
    TEST_ASSERT_EQUAL_STRING("RUST TOWN", hub_table[0]->name);
}
void test_rust_town_num_npcs(void) {
    TEST_ASSERT_EQUAL_UINT8(3u, hub_table[0]->num_npcs);
}
void test_rust_town_npc_names(void) {
    TEST_ASSERT_EQUAL_STRING("STEEVE",  hub_table[0]->npc_names[0]);
    TEST_ASSERT_EQUAL_STRING("TRADER",  hub_table[0]->npc_names[1]);
    TEST_ASSERT_EQUAL_STRING("DRIFTER", hub_table[0]->npc_names[2]);
}
void test_rust_town_dialog_ids(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, hub_table[0]->npc_dialog_ids[0]);
    TEST_ASSERT_EQUAL_UINT8(1u, hub_table[0]->npc_dialog_ids[1]);
    TEST_ASSERT_EQUAL_UINT8(2u, hub_table[0]->npc_dialog_ids[2]);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_hub_table_count);
    RUN_TEST(test_hub_table_has_rust_town);
    RUN_TEST(test_rust_town_num_npcs);
    RUN_TEST(test_rust_town_npc_names);
    RUN_TEST(test_rust_town_dialog_ids);
    return UNITY_END();
}
