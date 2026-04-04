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

void test_enemy_timer_does_not_fire_early(void) {
    enemy_spawn(10u, 20u);
    /* Timer starts at TURRET_FIRE_INTERVAL; should not fire until it reaches 0 */
    /* We test indirectly: no crash and active count unchanged after partial tick */
    enemy_tick_timers();   /* 1 frame */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_count_active());
}

void test_npc_type_constants_defined(void) {
    /* Compile-time presence; verify values match tmx_to_c.py NPC_TYPE_MAP */
    TEST_ASSERT_EQUAL_UINT8(0u, NPC_TYPE_TURRET);
    TEST_ASSERT_EQUAL_UINT8(1u, NPC_TYPE_CAR);
    TEST_ASSERT_EQUAL_UINT8(2u, NPC_TYPE_PEDESTRIAN);
    TEST_ASSERT_EQUAL_UINT8(0xFFu, DIR_NONE);
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
    RUN_TEST(test_enemy_timer_does_not_fire_early);
    return UNITY_END();
}
