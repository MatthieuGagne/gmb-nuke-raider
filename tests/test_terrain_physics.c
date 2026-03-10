/* tests/test_terrain_physics.c — AC2/AC3/AC4 terrain modifier tests */
#include "unity.h"
#include <gb/gb.h>
#include "../src/input.h"
#include "../src/config.h"
#include "player.h"
#include "track.h"

void setUp(void) {
    input = 0;
    prev_input = 0;
    mock_vram_clear();
    camera_init(88, 720);
    player_init();  /* resets px, py, vx=0, vy=0 */
}
void tearDown(void) {}

/* AC2: Sand produces lower velocity than road after N presses */
void test_sand_produces_lower_vx_than_road(void) {
    uint8_t i;
    int8_t road_vx, sand_vx;

    for (i = 0; i < (uint8_t)(PLAYER_MAX_SPEED + 2u); i++) {
        player_apply_physics(J_RIGHT, TILE_ROAD);
    }
    road_vx = player_get_vx();

    player_reset_vel();

    for (i = 0; i < (uint8_t)(PLAYER_MAX_SPEED + 2u); i++) {
        player_apply_physics(J_RIGHT, TILE_SAND);
    }
    sand_vx = player_get_vx();

    /* road_vx > sand_vx — TEST_ASSERT_GREATER_THAN_INT8(threshold, actual) */
    TEST_ASSERT_GREATER_THAN_INT8(sand_vx, road_vx);
}

/* AC3: Oil does not increase speed beyond entry velocity */
void test_oil_does_not_increase_vx(void) {
    int8_t entry_vx;
    uint8_t i;

    /* Build up speed on road */
    player_apply_physics(J_RIGHT, TILE_ROAD);
    player_apply_physics(J_RIGHT, TILE_ROAD);
    entry_vx = player_get_vx();   /* 2 */

    /* On oil: input ignored, no friction */
    for (i = 0; i < 4u; i++) {
        player_apply_physics(J_RIGHT, TILE_OIL);
    }

    TEST_ASSERT_TRUE(player_get_vx() <= entry_vx);
}

/* AC3: Oil does not decelerate (coasts) */
void test_oil_preserves_velocity_without_input(void) {
    int8_t entry_vx;

    player_apply_physics(J_RIGHT, TILE_ROAD);
    player_apply_physics(J_RIGHT, TILE_ROAD);
    entry_vx = player_get_vx();   /* 2 */

    /* No input on oil — should not decelerate */
    player_apply_physics(0, TILE_OIL);
    player_apply_physics(0, TILE_OIL);

    TEST_ASSERT_EQUAL_INT8(entry_vx, player_get_vx());
}

/* AC4: Boost increases vy in the upward direction (negative) */
void test_boost_increases_vy_upward(void) {
    /* No input, just boost tile — vy should go negative */
    player_apply_physics(0, TILE_BOOST);
    TEST_ASSERT_LESS_THAN_INT8(0, player_get_vy());
}

/* AC4: Boost is capped at TERRAIN_BOOST_MAX_SPEED, not PLAYER_MAX_SPEED */
void test_boost_capped_at_boost_max_speed(void) {
    uint8_t i;
    for (i = 0; i < 20u; i++) {
        player_apply_physics(J_UP, TILE_BOOST);
    }
    TEST_ASSERT_EQUAL_INT8(-(int8_t)TERRAIN_BOOST_MAX_SPEED, player_get_vy());
}

/* AC4: Boost allows exceeding normal max speed */
void test_boost_exceeds_normal_max_speed(void) {
    uint8_t i;
    for (i = 0; i < 20u; i++) {
        player_apply_physics(J_UP, TILE_BOOST);
    }
    /* vy should be more negative than -PLAYER_MAX_SPEED */
    TEST_ASSERT_LESS_THAN_INT8(-(int8_t)PLAYER_MAX_SPEED, player_get_vy());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_sand_produces_lower_vx_than_road);
    RUN_TEST(test_oil_does_not_increase_vx);
    RUN_TEST(test_oil_preserves_velocity_without_input);
    RUN_TEST(test_boost_increases_vy_upward);
    RUN_TEST(test_boost_capped_at_boost_max_speed);
    RUN_TEST(test_boost_exceeds_normal_max_speed);
    return UNITY_END();
}
