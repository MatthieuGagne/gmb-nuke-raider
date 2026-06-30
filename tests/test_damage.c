/* tests/test_damage.c — unit tests for the damage module */
#include "unity.h"
#include <gb/gb.h>
#include "../src/config.h"
#include "../src/damage.h"

void setUp(void)    { damage_init(); }
void tearDown(void) {}

/* --- init --- */

void test_init_sets_full_hp(void) {
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP, damage_get_hp());
}

void test_init_not_dead(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, damage_is_dead());
}

void test_init_not_invincible(void) {
    /* Apply immediately after init must deal damage (not blocked by i-frames) */
    damage_apply(1u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

/* --- damage_apply --- */

void test_apply_reduces_hp_by_one(void) {
    damage_apply(1u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

void test_apply_reduces_hp_by_amount(void) {
    damage_apply(3u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 3u, damage_get_hp());
}

void test_apply_clamps_to_zero_no_underflow(void) {
    damage_apply(100u);
    TEST_ASSERT_EQUAL_UINT8(0u, damage_get_hp());
}

void test_apply_exact_to_zero(void) {
    damage_apply(PLAYER_MAX_HP);
    TEST_ASSERT_EQUAL_UINT8(0u, damage_get_hp());
}

void test_apply_is_dead_at_zero(void) {
    damage_apply(PLAYER_MAX_HP);
    TEST_ASSERT_EQUAL_UINT8(1u, damage_is_dead());
}

void test_apply_not_dead_above_zero(void) {
    damage_apply(1u);
    TEST_ASSERT_EQUAL_UINT8(0u, damage_is_dead());
}

void test_apply_sets_invincibility(void) {
    damage_apply(1u);
    /* second apply must be blocked (i-frames active) */
    damage_apply(1u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

void test_apply_skips_second_hit_within_iframes(void) {
    uint8_t i;
    damage_apply(1u);
    /* tick 29 times (one short of cooldown expiry) */
    for (i = 0u; i < DAMAGE_INVINCIBILITY_FRAMES - 1u; i++) damage_tick();
    damage_apply(1u);  /* still invincible */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

void test_apply_hits_after_iframes_expire(void) {
    uint8_t i;
    damage_apply(1u);
    for (i = 0u; i < DAMAGE_INVINCIBILITY_FRAMES; i++) damage_tick();
    damage_apply(1u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 2u, damage_get_hp());
}

void test_apply_zero_amount_no_effect(void) {
    damage_apply(0u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP, damage_get_hp());
}

/* --- HEAVY armor damage reduction (#423) --- */

void test_armor_heavy_reduces_damage(void) {
    damage_set_armor_tier(1u);              /* HEAVY */
    damage_apply(5u);                        /* racer ram */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - (5u - ARMOR_HEAVY_REDUCTION),
                            damage_get_hp());
}

void test_armor_heavy_floors_one_damage(void) {
    damage_set_armor_tier(1u);              /* HEAVY */
    damage_apply(1u);                        /* wall — must still chip exactly 1 */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

void test_armor_heavy_floors_when_reduction_ge_amount(void) {
    damage_set_armor_tier(1u);              /* HEAVY */
    damage_apply(ARMOR_HEAVY_REDUCTION);     /* amount == reduction → floor to 1, not 0 */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

void test_armor_heavy_zero_amount_no_floor(void) {
    damage_set_armor_tier(1u);              /* HEAVY */
    damage_apply(0u);                        /* a 0 hit deals 0, NOT floored up to 1 */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP, damage_get_hp());
}

void test_armor_light_damage_unchanged(void) {
    damage_set_armor_tier(0u);              /* LIGHT — current behavior */
    damage_apply(5u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 5u, damage_get_hp());
}

void test_armor_init_resets_to_light(void) {
    damage_set_armor_tier(1u);              /* HEAVY ... */
    damage_init();                           /* ... then re-init must clear it back to LIGHT */
    damage_apply(5u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 5u, damage_get_hp());
}

void test_dead_player_not_damaged_further(void) {
    damage_apply(PLAYER_MAX_HP);        /* hp → 0 */
    uint8_t i;
    for (i = 0u; i < DAMAGE_INVINCIBILITY_FRAMES; i++) damage_tick();
    damage_apply(1u);                   /* should be skipped — already dead */
    TEST_ASSERT_EQUAL_UINT8(0u, damage_get_hp());
}

/* --- damage_tick --- */

void test_tick_no_effect_when_not_invincible(void) {
    /* No crash / underflow when ticking with zero cooldown */
    damage_tick();
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP, damage_get_hp());
}

void test_tick_30_times_expires_iframes(void) {
    uint8_t i;
    damage_apply(1u);
    for (i = 0u; i < DAMAGE_INVINCIBILITY_FRAMES; i++) damage_tick();
    /* now should be able to take damage again */
    damage_apply(1u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 2u, damage_get_hp());
}

void test_tick_exact_boundary_at_29_still_invincible(void) {
    uint8_t i;
    damage_apply(1u);
    for (i = 0u; i < DAMAGE_INVINCIBILITY_FRAMES - 1u; i++) damage_tick();
    damage_apply(1u);  /* tick 29: still invincible */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

/* --- damage_heal --- */

void test_heal_adds_hp(void) {
    damage_apply(3u);
    damage_heal(1u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 2u, damage_get_hp());
}

void test_heal_caps_at_max(void) {
    damage_apply(1u);
    damage_heal(100u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP, damage_get_hp());
}

void test_heal_exact_to_max(void) {
    damage_apply(2u);
    damage_heal(20u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP, damage_get_hp());
}

void test_heal_from_zero_restores_hp(void) {
    damage_apply(PLAYER_MAX_HP);        /* hp → 0 */
    damage_heal(20u);
    TEST_ASSERT_EQUAL_UINT8(20u, damage_get_hp());
}

void test_heal_zero_amount_no_effect(void) {
    damage_apply(2u);
    damage_heal(0u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 2u, damage_get_hp());
}

void test_heal_from_zero_not_dead_after_heal(void) {
    damage_apply(PLAYER_MAX_HP);
    damage_heal(1u);
    TEST_ASSERT_EQUAL_UINT8(0u, damage_is_dead());
}

void test_hp_exported_as_global(void) {
    extern uint8_t hp;
    damage_init();
    TEST_ASSERT_EQUAL_UINT8(damage_get_hp(), hp);
}

/* --- damage_get_hp --- */

void test_get_hp_after_init(void) {
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP, damage_get_hp());
}

void test_get_hp_decrements_with_apply(void) {
    damage_apply(1u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

void test_get_hp_increments_with_heal(void) {
    damage_apply(2u);
    damage_heal(1u);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_MAX_HP - 1u, damage_get_hp());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_sets_full_hp);
    RUN_TEST(test_init_not_dead);
    RUN_TEST(test_init_not_invincible);
    RUN_TEST(test_apply_reduces_hp_by_one);
    RUN_TEST(test_apply_reduces_hp_by_amount);
    RUN_TEST(test_apply_clamps_to_zero_no_underflow);
    RUN_TEST(test_apply_exact_to_zero);
    RUN_TEST(test_apply_is_dead_at_zero);
    RUN_TEST(test_apply_not_dead_above_zero);
    RUN_TEST(test_apply_sets_invincibility);
    RUN_TEST(test_apply_skips_second_hit_within_iframes);
    RUN_TEST(test_apply_hits_after_iframes_expire);
    RUN_TEST(test_apply_zero_amount_no_effect);
    RUN_TEST(test_armor_heavy_reduces_damage);
    RUN_TEST(test_armor_heavy_floors_one_damage);
    RUN_TEST(test_armor_heavy_floors_when_reduction_ge_amount);
    RUN_TEST(test_armor_heavy_zero_amount_no_floor);
    RUN_TEST(test_armor_light_damage_unchanged);
    RUN_TEST(test_armor_init_resets_to_light);
    RUN_TEST(test_dead_player_not_damaged_further);
    RUN_TEST(test_tick_no_effect_when_not_invincible);
    RUN_TEST(test_tick_30_times_expires_iframes);
    RUN_TEST(test_tick_exact_boundary_at_29_still_invincible);
    RUN_TEST(test_heal_adds_hp);
    RUN_TEST(test_heal_caps_at_max);
    RUN_TEST(test_heal_exact_to_max);
    RUN_TEST(test_heal_from_zero_restores_hp);
    RUN_TEST(test_heal_zero_amount_no_effect);
    RUN_TEST(test_heal_from_zero_not_dead_after_heal);
    RUN_TEST(test_get_hp_after_init);
    RUN_TEST(test_get_hp_decrements_with_apply);
    RUN_TEST(test_get_hp_increments_with_heal);
    RUN_TEST(test_hp_exported_as_global);
    return UNITY_END();
}
