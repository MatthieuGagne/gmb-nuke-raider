#include "unity.h"
#include "config.h"
#include "sfx.h"

void setUp(void) {}
void tearDown(void) {}

void test_debug_log_does_not_overlap_tick(void) {
    /* ring buffer occupies [DEBUG_LOG_ADDR, DEBUG_LOG_ADDR + DEBUG_LOG_SIZE) */
    /* LOG_IDX and TICK_ADDR must be outside that range */
    TEST_ASSERT_TRUE(DEBUG_LOG_IDX  >= DEBUG_LOG_ADDR + DEBUG_LOG_SIZE);
    TEST_ASSERT_TRUE(DEBUG_TICK_ADDR >= DEBUG_LOG_ADDR + DEBUG_LOG_SIZE);
    TEST_ASSERT_NOT_EQUAL(DEBUG_LOG_IDX, DEBUG_TICK_ADDR);
}

void test_debug_addresses_in_wram(void) {
    TEST_ASSERT_TRUE(DEBUG_LOG_ADDR  >= 0xC000U);
    TEST_ASSERT_TRUE(DEBUG_TICK_ADDR <= 0xDFFFU);
}

void test_sfx_count_defined(void) {
    TEST_ASSERT_EQUAL_UINT8(4u, SFX_COUNT);
}

void test_max_checkpoints_defined(void) {
    TEST_ASSERT_EQUAL_UINT8(8u, MAX_CHECKPOINTS);
}

void test_enemy_bullet_damage_defined(void) {
    TEST_ASSERT_EQUAL_UINT8(10u, ENEMY_BULLET_DAMAGE);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_debug_log_does_not_overlap_tick);
    RUN_TEST(test_debug_addresses_in_wram);
    RUN_TEST(test_sfx_count_defined);
    RUN_TEST(test_max_checkpoints_defined);
    RUN_TEST(test_enemy_bullet_damage_defined);
    return UNITY_END();
}
