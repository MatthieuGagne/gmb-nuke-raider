#include "unity.h"
#include "damage.h"

void setUp(void)    { damage_init(); }
void tearDown(void) {}

/* AC1: apply(1) reduces HP by 1 */
void test_damage_apply_reduces_hp(void) {
    uint8_t hp_before = damage_get_hp();
    damage_apply(1u);
    TEST_ASSERT_EQUAL_UINT8(hp_before - 1u, damage_get_hp());
}

/* AC1: HP never underflows past zero */
void test_damage_hp_clamps_to_zero(void) {
    damage_apply(255u);
    TEST_ASSERT_EQUAL_UINT8(0u, damage_get_hp());
}

/* AC2: second apply immediately after first is blocked by invincibility */
void test_damage_invincibility_blocks_double_hit(void) {
    uint8_t hp_after_first;
    damage_apply(1u);
    hp_after_first = damage_get_hp();
    damage_apply(1u);
    TEST_ASSERT_EQUAL_UINT8(hp_after_first, damage_get_hp());
}

/* AC2: after 30 damage_tick() calls invincibility expires */
void test_damage_invincibility_expires_after_30_ticks(void) {
    uint8_t i;
    damage_apply(1u);
    TEST_ASSERT_EQUAL_UINT8(1u, damage_is_invincible());
    for (i = 0u; i < 30u; i++) damage_tick();
    TEST_ASSERT_EQUAL_UINT8(0u, damage_is_invincible());
}

/* AC3: damage_is_dead() returns 1 after HP reaches 0 */
void test_damage_is_dead_after_zero_hp(void) {
    damage_apply(255u);
    TEST_ASSERT_EQUAL_UINT8(1u, damage_is_dead());
}

/* AC4: damage_heal(2) restores HP */
void test_damage_heal_restores_hp(void) {
    damage_apply(1u);
    /* expire invincibility so we can take another hit to lower HP reliably */
    {
        uint8_t i;
        for (i = 0u; i < 30u; i++) damage_tick();
    }
    damage_apply(1u);
    {
        uint8_t hp_before = damage_get_hp();
        {
            uint8_t i;
            for (i = 0u; i < 30u; i++) damage_tick();
        }
        damage_heal(DAMAGE_REPAIR_AMOUNT);
        TEST_ASSERT_EQUAL_UINT8(hp_before + DAMAGE_REPAIR_AMOUNT, damage_get_hp());
    }
}

/* AC4: heal caps at PLAYER_MAX_HP */
void test_damage_heal_caps_at_max(void) {
    damage_heal(255u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP, damage_get_hp());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_damage_apply_reduces_hp);
    RUN_TEST(test_damage_hp_clamps_to_zero);
    RUN_TEST(test_damage_invincibility_blocks_double_hit);
    RUN_TEST(test_damage_invincibility_expires_after_30_ticks);
    RUN_TEST(test_damage_is_dead_after_zero_hp);
    RUN_TEST(test_damage_heal_restores_hp);
    RUN_TEST(test_damage_heal_caps_at_max);
    return UNITY_END();
}
