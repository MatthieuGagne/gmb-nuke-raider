/* tests/test_vehicle_physics.c */
#include "unity.h"
#include <gb/gb.h>
#include "vehicle_physics.h"
#include "track.h"
#include "config.h"

void setUp(void) {
    active_map_w = 8u;    /* 8 tiles * 8px = 64px; max px = 48 */
    active_map_h = 8u;
    mock_vram_clear();
}
void tearDown(void) {}

/* ---- vehicle_apply_friction: friction-only (PRE gear-accel) ---- */

/* ROAD with gas on the moving axis: no friction on that axis; perpendicular axis
 * loses PLAYER_FRICTION. gas=1, dir=DIR_R (DX!=0): vx relieved; vy (DY==0) -1. */
void test_veh_friction_road_gas_axis_relieved(void) {
    int8_t vx = 4, vy = 4;
    vehicle_apply_friction(&vx, &vy, TILE_ROAD, 1u, 2u /*DIR_R*/);
    TEST_ASSERT_EQUAL_INT8(4, vx);   /* gassed axis: no friction */
    TEST_ASSERT_EQUAL_INT8(3, vy);   /* perpendicular: -PLAYER_FRICTION(1) */
}

/* SAND doubles friction on the non-gassed axis vs ROAD. */
void test_veh_friction_sand_doubles(void) {
    int8_t road_vy, sand_vy;
    {
        int8_t vx = 0, vy = -4;
        vehicle_apply_friction(&vx, &vy, TILE_ROAD, 1u, 2u /*DIR_R, DY==0*/);
        road_vy = vy;   /* -4 + PLAYER_FRICTION(1) = -3 */
    }
    {
        int8_t vx = 0, vy = -4;
        vehicle_apply_friction(&vx, &vy, TILE_SAND, 1u, 2u /*DIR_R*/);
        sand_vy = vy;   /* -4 + 2*PLAYER_FRICTION = -2 */
    }
    TEST_ASSERT_EQUAL_INT8(-3, road_vy);
    TEST_ASSERT_EQUAL_INT8(-2, sand_vy);
    TEST_ASSERT_GREATER_THAN_INT8(road_vy, sand_vy); /* sand decelerates faster */
}

/* OIL zeroes friction (frictionless slide): velocity unchanged. The caller passes
 * gas=0 on oil; friction is zero regardless of the gas-axis decision. */
void test_veh_friction_oil_none(void) {
    int8_t vx = 4, vy = 4;
    vehicle_apply_friction(&vx, &vy, TILE_OIL, 0u /*oil disables gas*/, 2u);
    TEST_ASSERT_EQUAL_INT8(4, vx);
    TEST_ASSERT_EQUAL_INT8(4, vy);
}

/* vehicle_apply_friction does NOT apply boost: on TILE_BOOST it only does friction. */
void test_veh_friction_ignores_boost(void) {
    int8_t vx = 0, vy = 0;
    vehicle_apply_friction(&vx, &vy, TILE_BOOST, 1u, 0u /*DIR_T*/);
    TEST_ASSERT_EQUAL_INT8(0, vx);   /* boost delta is boost_clamp's job, not friction's */
    TEST_ASSERT_EQUAL_INT8(0, vy);
}

/* ---- vehicle_apply_boost_clamp: boost-delta + clamp (POST gear-accel) ---- */

/* BOOST kicks vy negative by TERRAIN_BOOST_DELTA and clamps to boost max speed. */
void test_veh_boost_clamp_accelerates_up(void) {
    int8_t vx = 0, vy = 0;
    vehicle_apply_boost_clamp(&vx, &vy, TILE_BOOST, TERRAIN_BOOST_MAX_SPEED);
    TEST_ASSERT_LESS_THAN_INT8(0, vy);    /* boost delta moved vy negative (upward) */
    TEST_ASSERT_EQUAL_INT8(0, vx);        /* x untouched by boost */
}

/* boost_clamp does NOT apply friction: ROAD leaves velocity unchanged below clamp. */
void test_veh_boost_clamp_no_friction(void) {
    int8_t vx = 3, vy = 3;
    vehicle_apply_boost_clamp(&vx, &vy, TILE_ROAD, 8u);
    TEST_ASSERT_EQUAL_INT8(3, vx);
    TEST_ASSERT_EQUAL_INT8(3, vy);
}

/* max_speed clamp: a velocity above max_speed is clamped to ±max_speed. */
void test_veh_boost_clamp_max_speed(void) {
    int8_t vx = 100, vy = -100;
    vehicle_apply_boost_clamp(&vx, &vy, TILE_ROAD, 5u);
    TEST_ASSERT_EQUAL_INT8(5, vx);
    TEST_ASSERT_EQUAL_INT8(-5, vy);
}

/* ---- vehicle_apply_physics: gearless convenience = friction then boost_clamp ---- */

/* The convenience equals calling friction then boost_clamp with NO accel between.
 * Verify composition for ROAD (friction only). */
void test_veh_physics_composes_road(void) {
    int8_t cx = 4, cy = 4;          /* via convenience */
    int8_t fx = 4, fy = 4;          /* via split: friction then boost_clamp */
    vehicle_apply_physics(&cx, &cy, TILE_ROAD, 1u, 2u /*DIR_R*/, 8u);
    vehicle_apply_friction(&fx, &fy, TILE_ROAD, 1u, 2u);
    vehicle_apply_boost_clamp(&fx, &fy, TILE_ROAD, 8u);
    TEST_ASSERT_EQUAL_INT8(fx, cx);
    TEST_ASSERT_EQUAL_INT8(fy, cy);
}

/* Composition holds on BOOST (friction then boost-delta then clamp). */
void test_veh_physics_composes_boost(void) {
    int8_t cx = 0, cy = 0;
    int8_t fx = 0, fy = 0;
    vehicle_apply_physics(&cx, &cy, TILE_BOOST, 1u, 0u /*DIR_T*/, TERRAIN_BOOST_MAX_SPEED);
    vehicle_apply_friction(&fx, &fy, TILE_BOOST, 1u, 0u);
    vehicle_apply_boost_clamp(&fx, &fy, TILE_BOOST, TERRAIN_BOOST_MAX_SPEED);
    TEST_ASSERT_EQUAL_INT8(fx, cx);
    TEST_ASSERT_EQUAL_INT8(fy, cy);
    TEST_ASSERT_LESS_THAN_INT8(0, cy);   /* boosted upward */
}

/* ---- vehicle_step_axis_x / _y: slide collision ---- */

static const uint8_t road_map_8x8[8u * 8u] = {
    1,1,1,0,1,1,1,1,   /* col 3 = WALL */
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
};

/* X step into a wall column is blocked: px returned unchanged. */
void test_veh_step_x_blocked_by_wall(void) {
    static const uint8_t road_pass[8] = {255,255,255,255,255,255,255,255}; /* all 8 px passable */
    static const uint8_t wall_block[8] = {0,0,0,0,0,0,0,0};
    track_test_set_map(road_map_8x8, 8u, 8u);
    track_test_set_collision_mask(1u, road_pass);   /* tile 1 ROAD: fully passable */
    track_test_set_collision_mask(0u, wall_block);  /* tile 0 WALL: fully blocked */
    /* px=8 (footprint cols 1..2 road); vx=+8 -> px=16, right corner px+15=31 -> col 3 WALL */
    {
        int16_t out = vehicle_step_axis_x(8, 0, 8);
        TEST_ASSERT_EQUAL_INT16(8, out);  /* blocked: unchanged */
    }
}

/* X step on clear road advances by vx. */
void test_veh_step_x_clear_advances(void) {
    static const uint8_t road_pass[8] = {255,255,255,255,255,255,255,255};
    static const uint8_t wall_block[8] = {0,0,0,0,0,0,0,0};
    static const uint8_t all_road[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    track_test_set_map(all_road, 8u, 8u);
    track_test_set_collision_mask(1u, road_pass);
    track_test_set_collision_mask(0u, wall_block);
    {
        int16_t out = vehicle_step_axis_x(8, 0, 4);
        TEST_ASSERT_EQUAL_INT16(12, out);
    }
}

/* Y step into a wall row is blocked: py returned unchanged. */
void test_veh_step_y_blocked_by_wall(void) {
    static const uint8_t road_pass[8] = {255,255,255,255,255,255,255,255};
    static const uint8_t wall_block[8] = {0,0,0,0,0,0,0,0};
    static const uint8_t row_wall[8u * 8u] = {
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        0,0,0,0,0,0,0,0,   /* row 3 = WALL */
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
    };
    track_test_set_map(row_wall, 8u, 8u);
    track_test_set_collision_mask(1u, road_pass);
    track_test_set_collision_mask(0u, wall_block);
    {
        int16_t out = vehicle_step_axis_y(8, 8, 8); /* py=8 -> 16, bottom corner 31 -> row 3 WALL */
        TEST_ASSERT_EQUAL_INT16(8, out);
    }
}

/* In-bounds clamp: moving X past the right map edge is blocked. */
void test_veh_step_x_oob_right_blocked(void) {
    static const uint8_t road_pass[8] = {255,255,255,255,255,255,255,255};
    static const uint8_t all_road[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    track_test_set_map(all_road, 8u, 8u);
    track_test_set_collision_mask(1u, road_pass);
    /* active_map_w=8 -> max px = 64-16 = 48. px=48, vx=+4 -> 52 > 48 -> blocked. */
    {
        int16_t out = vehicle_step_axis_x(48, 0, 4);
        TEST_ASSERT_EQUAL_INT16(48, out);
    }
}

/* In-bounds clamp: moving X below 0 is blocked. */
void test_veh_step_x_oob_left_blocked(void) {
    static const uint8_t road_pass[8] = {255,255,255,255,255,255,255,255};
    static const uint8_t all_road[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    track_test_set_map(all_road, 8u, 8u);
    track_test_set_collision_mask(1u, road_pass);
    {
        int16_t out = vehicle_step_axis_x(0, 0, -4); /* -4 < 0 -> blocked */
        TEST_ASSERT_EQUAL_INT16(0, out);
    }
}

int main(void) {
    UNITY_BEGIN();
    /* vehicle_apply_friction */
    RUN_TEST(test_veh_friction_road_gas_axis_relieved);
    RUN_TEST(test_veh_friction_sand_doubles);
    RUN_TEST(test_veh_friction_oil_none);
    RUN_TEST(test_veh_friction_ignores_boost);
    /* vehicle_apply_boost_clamp */
    RUN_TEST(test_veh_boost_clamp_accelerates_up);
    RUN_TEST(test_veh_boost_clamp_no_friction);
    RUN_TEST(test_veh_boost_clamp_max_speed);
    /* vehicle_apply_physics convenience (composition) */
    RUN_TEST(test_veh_physics_composes_road);
    RUN_TEST(test_veh_physics_composes_boost);
    /* vehicle_step_axis_x / _y */
    RUN_TEST(test_veh_step_x_blocked_by_wall);
    RUN_TEST(test_veh_step_x_clear_advances);
    RUN_TEST(test_veh_step_y_blocked_by_wall);
    RUN_TEST(test_veh_step_x_oob_right_blocked);
    RUN_TEST(test_veh_step_x_oob_left_blocked);
    return UNITY_END();
}
