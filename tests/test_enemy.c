#include "unity.h"
#include "enemy.h"
#include "player.h"   /* player_dir_t */
#include "camera.h"   /* cam_x, cam_y */

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

/* ax == ay tie → toward_x = (ax > ay) = 0 → NNE-side direction */
void test_enemy_direction_to_player_down_right(void) {
    /* Was DIR_RB; 3-threshold: ax=ay=64, toward_x=0, SE quadrant → DIR_SSE */
    TEST_ASSERT_EQUAL_INT(DIR_SSE, enemy_dir_to_pixel(0u, 0u, 64, 64));
}
void test_enemy_direction_to_player_up_left(void) {
    /* Was DIR_LT; 3-threshold: ax=ay=80, toward_x=0, NW quadrant → DIR_NNW */
    TEST_ASSERT_EQUAL_INT(DIR_NNW, enemy_dir_to_pixel(10u, 10u, 0, 0));
}

/* 16-direction tests — intermediate sectors */
void test_enemy_direction_nne(void) {
    /* ax=10 < ay=15, NE quadrant → DIR_NNE */
    TEST_ASSERT_EQUAL_INT(DIR_NNE, enemy_dir_to_pixel(0u, 0u, 10, -15));
}
void test_enemy_direction_ene(void) {
    /* ax=15 > ay=10, NE quadrant → DIR_ENE */
    TEST_ASSERT_EQUAL_INT(DIR_ENE, enemy_dir_to_pixel(0u, 0u, 15, -10));
}
void test_enemy_direction_ese(void) {
    TEST_ASSERT_EQUAL_INT(DIR_ESE, enemy_dir_to_pixel(0u, 0u, 15, 10));
}
void test_enemy_direction_sse(void) {
    TEST_ASSERT_EQUAL_INT(DIR_SSE, enemy_dir_to_pixel(0u, 0u, 10, 15));
}
void test_enemy_direction_ssw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_SSW, enemy_dir_to_pixel(0u, 0u, -10, 15));
}
void test_enemy_direction_wsw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_WSW, enemy_dir_to_pixel(0u, 0u, -15, 10));
}
void test_enemy_direction_wnw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_WNW, enemy_dir_to_pixel(0u, 0u, -15, -10));
}
void test_enemy_direction_nnw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_NNW, enemy_dir_to_pixel(0u, 0u, -10, -15));
}

void test_enemy_spawn_timer_is_wind_up(void) {
    enemy_spawn(10u, 20u);
    TEST_ASSERT_EQUAL_UINT8(TURRET_WIND_UP, enemy_get_timer(0u));
}

void test_enemy_three_turrets_timer_at_wind_up(void) {
    enemy_spawn(4u, 22u);
    enemy_spawn(15u, 47u);
    enemy_spawn(5u, 72u);
    TEST_ASSERT_EQUAL_UINT8(TURRET_WIND_UP, enemy_get_timer(0u));
    TEST_ASSERT_EQUAL_UINT8(TURRET_WIND_UP, enemy_get_timer(1u));
    TEST_ASSERT_EQUAL_UINT8(TURRET_WIND_UP, enemy_get_timer(2u));
}

void test_enemy_timer_does_not_fire_during_wind_up(void) {
    enemy_spawn(10u, 20u);
    TEST_ASSERT_EQUAL_UINT8(TURRET_WIND_UP, enemy_get_timer(0u));
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_count_active());
}

/* Visibility helper tests — set cam_x/cam_y directly */
void test_enemy_visible_when_on_screen(void) {
    /* ty=10: world_y=80. cam_y=0 → vis_y=80-0+16=96 ∈ [0,160) ✓
     * tx=10: world_oam_x=88. cam_x=0 → vis_x=88 ∈ [0,168) ✓ */
    cam_y = 0u;
    cam_x = 0u;
    enemy_spawn(10u, 10u);
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_is_screen_visible(0u));
}

void test_enemy_not_visible_when_below_screen(void) {
    /* ty=20: world_y=160. cam_y=0 → vis_y=160-0+16=176 ≥ 160 → off screen */
    cam_y = 0u;
    cam_x = 0u;
    enemy_spawn(10u, 20u);
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_is_screen_visible(0u));
}

void test_enemy_not_visible_when_above_screen(void) {
    /* ty=1: world_y=8. cam_y=100 → vis_y=8-100+16=-76 < 0 → off screen */
    cam_y = 100u;
    cam_x = 0u;
    enemy_spawn(10u, 1u);
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_is_screen_visible(0u));
}

void test_enemy_not_visible_when_off_screen_right(void) {
    /* tx=22: oam_x=22*8+8=184. cam_x=0 → vis_x=184 ≥ 168 → off screen */
    cam_y = 0u;
    cam_x = 0u;
    enemy_spawn(22u, 10u);
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_is_screen_visible(0u));
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
    RUN_TEST(test_enemy_direction_nne);
    RUN_TEST(test_enemy_direction_ene);
    RUN_TEST(test_enemy_direction_ese);
    RUN_TEST(test_enemy_direction_sse);
    RUN_TEST(test_enemy_direction_ssw);
    RUN_TEST(test_enemy_direction_wsw);
    RUN_TEST(test_enemy_direction_wnw);
    RUN_TEST(test_enemy_direction_nnw);
    RUN_TEST(test_enemy_spawn_timer_is_wind_up);
    RUN_TEST(test_enemy_three_turrets_timer_at_wind_up);
    RUN_TEST(test_enemy_timer_does_not_fire_during_wind_up);
    RUN_TEST(test_enemy_visible_when_on_screen);
    RUN_TEST(test_enemy_not_visible_when_below_screen);
    RUN_TEST(test_enemy_not_visible_when_above_screen);
    RUN_TEST(test_enemy_not_visible_when_off_screen_right);
    RUN_TEST(test_enemy_spawn_sets_type_turret);
    RUN_TEST(test_enemy_spawn_sets_dir_none);
    RUN_TEST(test_turret_dir_enum_has_16_values);
    RUN_TEST(test_turret_constants_values);
    return UNITY_END();
}
