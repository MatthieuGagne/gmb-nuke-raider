#include "unity.h"
#include "../src/config.h"

void setUp(void) {}
void tearDown(void) {}

void test_max_npcs_sane(void) {
    /* At least 6 NPCs required by current design; see src/config.h */
    TEST_ASSERT_GREATER_OR_EQUAL(6, MAX_NPCS);
}

void test_max_sprites_sane(void) {
    /* OAM hardware limit is 40; pool must cover full OAM budget */
    TEST_ASSERT_GREATER_OR_EQUAL(40, MAX_SPRITES);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_max_npcs_sane);
    RUN_TEST(test_max_sprites_sane);
    return UNITY_END();
}
