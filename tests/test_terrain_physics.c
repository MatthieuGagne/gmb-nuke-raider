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

/* AC2: Sand decelerates faster than road (double friction).
 * With PLAYER_ACCEL == PLAYER_FRICTION, gas caps vx/vy at 1, so the difference
 * only shows at higher speeds. Build speed via boost (no J_A), then coast on each
 * terrain. Sand (friction=2) clears velocity in fewer frames than road (friction=1). */
void test_sand_decelerates_faster_than_road(void) {
    uint8_t i;
    int8_t road_vy, sand_vy;

    /* Build vy to -TERRAIN_BOOST_MAX_SPEED via boost */
    for (i = 0; i < 20u; i++) {
        player_apply_physics(0, TILE_BOOST);
    }
    /* Coast on road for 2 frames: vy goes -8 → -7 → -6 (friction=1 per frame) */
    player_apply_physics(0, TILE_ROAD);
    player_apply_physics(0, TILE_ROAD);
    road_vy = player_get_vy();

    /* Reset and rebuild the same velocity */
    player_reset_vel();
    for (i = 0; i < 20u; i++) {
        player_apply_physics(0, TILE_BOOST);
    }
    /* Coast on sand for 2 frames: vy goes -8 → -6 → -4 (friction=2 per frame) */
    player_apply_physics(0, TILE_SAND);
    player_apply_physics(0, TILE_SAND);
    sand_vy = player_get_vy();

    /* Sand decelerates faster: |sand_vy| < |road_vy|, i.e. sand_vy > road_vy (both negative) */
    TEST_ASSERT_GREATER_THAN_INT8(road_vy, sand_vy);
}

/* AC3: Oil does not increase speed beyond entry velocity */
void test_oil_does_not_increase_vx(void) {
    int8_t entry_vx;
    uint8_t i;

    /* Build up speed on road */
    player_apply_physics(J_RIGHT | J_A, TILE_ROAD);
    player_apply_physics(J_RIGHT | J_A, TILE_ROAD);
    entry_vx = player_get_vx();   /* 1 (PLAYER_ACCEL; friction and gas cancel each extra step) */

    /* On oil: input ignored, no friction */
    for (i = 0; i < 4u; i++) {
        player_apply_physics(J_RIGHT, TILE_OIL);
    }

    TEST_ASSERT_TRUE(player_get_vx() <= entry_vx);
}

/* AC3: Oil does not decelerate (coasts) */
void test_oil_preserves_velocity_without_input(void) {
    int8_t entry_vx;

    player_apply_physics(J_RIGHT | J_A, TILE_ROAD);
    player_apply_physics(J_RIGHT | J_A, TILE_ROAD);
    entry_vx = player_get_vx();   /* 1 (PLAYER_ACCEL) */

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
    RUN_TEST(test_sand_decelerates_faster_than_road);
    RUN_TEST(test_oil_does_not_increase_vx);
    RUN_TEST(test_oil_preserves_velocity_without_input);
    RUN_TEST(test_boost_increases_vy_upward);
    RUN_TEST(test_boost_capped_at_boost_max_speed);
    RUN_TEST(test_boost_exceeds_normal_max_speed);
    return UNITY_END();
}
