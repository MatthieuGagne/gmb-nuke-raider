#include "unity.h"
#include "enemy.h"
#include "player.h"   /* player_dir_t */

void setUp(void) { enemy_init_empty(); }
void tearDown(void) {}

/* enemy_init_empty() zeros the pool without scanning the map —
 * used by tests to get a clean state without touching hardware. */

void test_enemy_pool_empty_after_init(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_count_active());
}

void test_enemy_spawn_and_active(void) {
    enemy_spawn(10u, 20u);   /* tile coords */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_count_active());
}

void test_enemy_blocks_tile_active(void) {
    enemy_spawn(10u, 20u);
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_blocks_tile(10u, 20u));
}

void test_enemy_blocks_tile_inactive(void) {
    /* No spawn — tile should not be blocked */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_blocks_tile(10u, 20u));
}

void test_enemy_blocks_tile_wrong_position(void) {
    enemy_spawn(10u, 20u);
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_blocks_tile(5u, 5u));
}

void test_enemy_direction_to_player_right(void) {
    /* Turret at tile (0,0) = pixel (0,0); player at pixel (64,0) → DIR_R */
    TEST_ASSERT_EQUAL_INT(DIR_R, enemy_dir_to_pixel(0u, 0u, 64, 0));
}

void test_enemy_direction_to_player_down(void) {
    TEST_ASSERT_EQUAL_INT(DIR_B, enemy_dir_to_pixel(0u, 0u, 0, 64));
}

void test_enemy_direction_to_player_down_right(void) {
    TEST_ASSERT_EQUAL_INT(DIR_RB, enemy_dir_to_pixel(0u, 0u, 64, 64));
}

void test_enemy_direction_to_player_up_left(void) {
    TEST_ASSERT_EQUAL_INT(DIR_LT, enemy_dir_to_pixel(10u, 10u, 0, 0));
    /* turret pixel = (80, 80); player at (0,0): dx=-80, dy=-80 → DIR_LT */
}

void test_enemy_timer_fires_on_first_frame(void) {
    enemy_spawn(10u, 20u);
    /* Timer starts at 0 — fires on the very first update; active count unchanged */
    enemy_tick_timers();   /* 1 frame — timer was already 0, stays 0 until fire */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_count_active());
}

void test_enemy_timer_zero_at_spawn(void) {
    enemy_spawn(10u, 20u);
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_get_timer(0u));
}

void test_enemy_three_turrets_timer_all_zero(void) {
    enemy_spawn(4u, 22u);
    enemy_spawn(15u, 47u);
    enemy_spawn(5u, 72u);
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_get_timer(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_get_timer(1u));
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_get_timer(2u));
}

void test_enemy_spawn_sets_type_turret(void) {
    enemy_spawn(5u, 5u);
    TEST_ASSERT_EQUAL_UINT8(NPC_TYPE_TURRET, enemy_get_type(0u));
}

void test_enemy_spawn_sets_dir_none(void) {
    enemy_spawn(5u, 5u);
    TEST_ASSERT_EQUAL_UINT8(DIR_NONE, enemy_get_dir(0u));
}

void test_turret_dir_enum_has_16_values(void) {
    /* Compile-time check: new enum constants exist and are in range 8-15 */
    TEST_ASSERT_EQUAL_INT(8,  DIR_NNE);
    TEST_ASSERT_EQUAL_INT(9,  DIR_ENE);
    TEST_ASSERT_EQUAL_INT(10, DIR_ESE);
    TEST_ASSERT_EQUAL_INT(11, DIR_SSE);
    TEST_ASSERT_EQUAL_INT(12, DIR_SSW);
    TEST_ASSERT_EQUAL_INT(13, DIR_WSW);
    TEST_ASSERT_EQUAL_INT(14, DIR_WNW);
    TEST_ASSERT_EQUAL_INT(15, DIR_NNW);
}

void test_npc_type_constants_defined(void) {
    /* Compile-time presence; verify values match tmx_to_c.py NPC_TYPE_MAP */
    TEST_ASSERT_EQUAL_UINT8(0u, NPC_TYPE_TURRET);
    TEST_ASSERT_EQUAL_UINT8(1u, NPC_TYPE_CAR);
    TEST_ASSERT_EQUAL_UINT8(2u, NPC_TYPE_PEDESTRIAN);
    TEST_ASSERT_EQUAL_UINT8(0xFFu, DIR_NONE);
}

void test_turret_constants_values(void) {
    TEST_ASSERT_EQUAL_UINT8(45u, TURRET_FIRE_INTERVAL);
    TEST_ASSERT_EQUAL_UINT8(30u, TURRET_WIND_UP);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_npc_type_constants_defined);
    RUN_TEST(test_enemy_pool_empty_after_init);
    RUN_TEST(test_enemy_spawn_and_active);
    RUN_TEST(test_enemy_blocks_tile_active);
    RUN_TEST(test_enemy_blocks_tile_inactive);
    RUN_TEST(test_enemy_blocks_tile_wrong_position);
    RUN_TEST(test_enemy_direction_to_player_right);
    RUN_TEST(test_enemy_direction_to_player_down);
    RUN_TEST(test_enemy_direction_to_player_down_right);
    RUN_TEST(test_enemy_direction_to_player_up_left);
    RUN_TEST(test_enemy_timer_fires_on_first_frame);
    RUN_TEST(test_enemy_timer_zero_at_spawn);
    RUN_TEST(test_enemy_three_turrets_timer_all_zero);
    RUN_TEST(test_enemy_spawn_sets_type_turret);
    RUN_TEST(test_enemy_spawn_sets_dir_none);
    RUN_TEST(test_turret_dir_enum_has_16_values);
    RUN_TEST(test_turret_constants_values);
    return UNITY_END();
}
