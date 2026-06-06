/* tests/test_racer.c */
#include "unity.h"
#include "racer.h"
#include "config.h"
#include "track.h"
#include "checkpoint.h"
#include "race_state.h"
#include "player.h"    /* player_dir_t: DIR_T, DIR_B, etc. */
#include "projectile.h"

extern int16_t cam_y;

void setUp(void) {
    cam_y = 0;
    racer_init_empty();
    projectile_init(0u);
}
void tearDown(void) {}

void test_racer_inactive_after_init_empty(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, racer_update());
}

void test_racer_advances_waypoint_when_close(void) {
    uint8_t wp_tx[2] = { 10u, 20u };
    uint8_t wp_ty[2] = { 10u, 10u };
    racer_spawn_for_test(84u, 84u, wp_tx, wp_ty, 2u, CHECKPOINT_DIR_S, 1u);
    racer_update();
    TEST_ASSERT_EQUAL_UINT8(1u, racer_get_wp_idx(0u));
}

void test_racer_finish_triggers_game_over(void) {
    /* Map: 8x8 with tile index 12 (TILE_FINISH) at position (5,6).
     * Flat uint8_t array row-major: row 6 starts at offset 6*8=48, col 5 = index 53. */
    static const uint8_t finish_map[8*8] = {
        1,1,1,1,1,1,1,1,  /* row 0 */
        1,1,1,1,1,1,1,1,  /* row 1 */
        1,1,1,1,1,1,1,1,  /* row 2 */
        1,1,1,1,1,1,1,1,  /* row 3 */
        1,1,1,1,1,1,1,1,  /* row 4 */
        1,1,1,1,1,1,1,1,  /* row 5 */
        1,1,1,1,1,18,1,1, /* row 6: tile 18=TILE_FINISH at col 5 */
        1,1,1,1,1,1,1,1,  /* row 7 */
    };
    uint8_t wp_tx[1] = { 5u };
    uint8_t wp_ty[1] = { 5u };
    track_test_set_map(finish_map, 8u, 8u);
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 1u);
    racer_place_on_finish_for_test(5u, 6u, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, racer_update());
}

void test_racer_finish_wrong_direction_no_game_over(void) {
    /* Finish line at tile (5,6). Racer placed on finish tile but moving NORTH
     * (waypoint at ty=0 north of the finish) — direction mismatch with CHECKPOINT_DIR_S. */
    static const uint8_t finish_map[8*8] = {
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,18,1,1,
        1,1,1,1,1,1,1,1,
    };
    /* Waypoint directly north of finish at tile (5,0): delta dx=0, dy<0 → DIR_T */
    uint8_t wp_tx[1] = { 5u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(finish_map, 8u, 8u);
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 1u);
    /* Place racer centre at tile (5,6) = pixel (44,52), heading toward waypoint (5,0) */
    racer_set_pos_for_test(0u, 36, 52);
    TEST_ASSERT_EQUAL_UINT8(0u, racer_update());
}

void test_racer_wraps_waypoints(void) {
    uint8_t wp_tx[2] = { 10u, 20u };
    uint8_t wp_ty[2] = { 10u, 10u };
    racer_spawn_for_test(84u, 84u, wp_tx, wp_ty, 2u, CHECKPOINT_DIR_S, 1u);
    racer_set_wp_idx_for_test(0u, 1u);
    racer_set_pos_for_test(0u, 164, 84);
    racer_update();
    TEST_ASSERT_EQUAL_UINT8(0u, racer_get_wp_idx(0u));
}

void test_racer_no_finish_before_all_laps_done(void) {
    /* Racer on finish tile with 2 laps done out of 3 required — must NOT trigger. */
    static const uint8_t finish_map[8*8] = {
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,18,1,1,
        1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 5u };
    uint8_t wp_ty[1] = { 5u };
    track_test_set_map(finish_map, 8u, 8u);
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    race_state_set_laps_for_test(0u, 1u);  /* 1 of 3 laps done — 2 more needed */
    racer_place_on_finish_for_test(5u, 6u, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(0u, racer_update());
}

void test_racer_finishes_after_all_laps_done(void) {
    /* Racer on finish tile with exactly lap_total laps done — must trigger. */
    static const uint8_t finish_map[8*8] = {
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,18,1,1,
        1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 5u };
    uint8_t wp_ty[1] = { 5u };
    track_test_set_map(finish_map, 8u, 8u);
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    race_state_set_laps_for_test(0u, 2u);  /* 2 of 3 laps done — one more finishes */
    racer_place_on_finish_for_test(5u, 6u, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, racer_update());
}

void test_racer_active_exported_as_global(void) {
    extern uint8_t racer_active[];
    racer_init_empty();
    TEST_ASSERT_EQUAL_UINT8(0u, racer_active[0]);
}

void test_racer_4corner_blocks_when_corner_hits_wall(void) {
    /* Map 8×4: col 3 = wall. Racer at px=8, py=0, moving DIR_R.
     * vx=6 injected: after gear physics vx is clamped to RACER_GEAR1_MAX_SPEED, new_px=10.
     * Right corner = (10+15, 0+2) = (25, 2) → tx=3 = WALL.
     * Centre = (10, 0) → tx=1 = ROAD — old single-point check would allow move. */
    static const uint8_t map[4u * 8u] = {
        1,1,1,0,1,1,1,1,
        1,1,1,0,1,1,1,1,
        1,1,1,0,1,1,1,1,
        1,1,1,0,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 7u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(map, 8u, 4u);
    racer_spawn_for_test(8, 0, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_E, 1u);
    racer_set_vel_for_test(0u, 6, 0);
    racer_update();
    TEST_ASSERT_EQUAL_INT16(8, racer_get_px(0u));
    TEST_ASSERT_EQUAL_INT8(0, racer_get_vx(0u));
}

void test_racer_slides_along_wall_on_y_collision(void) {
    /* Map 8×8: row 3 = wall. Racer at px=8, py=8, DIR_RB, vel (4,4) injected.
     * Y blocked: bottom corner hits ty=3. X clear: px advances. py stays at 8. */
    static const uint8_t map[8u * 8u] = {
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        0,0,0,0,0,0,0,0,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 7u };
    uint8_t wp_ty[1] = { 7u };
    track_test_set_map(map, 8u, 8u);
    racer_spawn_for_test(8, 8, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 1u);
    racer_set_vel_for_test(0u, 4, 4);
    racer_update();
    TEST_ASSERT_EQUAL_INT16(8, racer_get_py(0u));
    TEST_ASSERT_GREATER_THAN_INT16(8, racer_get_px(0u));
}

void test_racer_accelerates_from_rest(void) {
    /* All-road map. Racer at (24, 48), waypoint at (3, 0) → DIR_T.
     * After 3 updates vy should be negative (accelerating north). */
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 3u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(flat_map, 8u, 8u);
    racer_spawn_for_test(24, 48, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_update();
    racer_update();
    racer_update();
    TEST_ASSERT_LESS_THAN_INT8(0, racer_get_vy(0u));
}

void test_racer_wall_collision_zeroes_vx_and_gear(void) {
    /* Map 8×4: col 2 = wall. Racer at px=0, py=0, gear=2, vx=5 injected.
     * X move blocked by wall: vx must be 0 and gear must be 0 after update. */
    static const uint8_t map[4u * 8u] = {
        1,1,0,1,1,1,1,1,
        1,1,0,1,1,1,1,1,
        1,1,0,1,1,1,1,1,
        1,1,0,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 7u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(map, 8u, 4u);
    racer_spawn_for_test(0, 0, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_E, 1u);
    racer_set_vel_for_test(0u, 5, 0);
    racer_set_gear_for_test(0u, 2u);
    racer_update();
    TEST_ASSERT_EQUAL_INT8(0, racer_get_vx(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, racer_get_gear(0u));
}

/* ---- Terrain interaction tests ---- */

void test_racer_sand_doubles_friction(void) {
    /* All-sand map (tile 9). Racer at (0,32), waypoint east -> DIR_R (DY=0).
     * Inject vy=-4 (perpendicular). After 1 frame:
     *   road: fric_y = PLAYER_FRICTION     = 1 -> vy=-3
     *   sand: fric_y = PLAYER_FRICTION * 2 = 2 -> vy=-2
     * sand_vy (-2) > road_vy (-3): less negative = decelerated faster. */
    static const uint8_t sand_map[8u * 8u] = {
        9,9,9,9,9,9,9,9,
        9,9,9,9,9,9,9,9,
        9,9,9,9,9,9,9,9,
        9,9,9,9,9,9,9,9,
        9,9,9,9,9,9,9,9,
        9,9,9,9,9,9,9,9,
        9,9,9,9,9,9,9,9,
        9,9,9,9,9,9,9,9,
    };
    static const uint8_t road_map[8u * 8u] = {
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 7u };
    uint8_t wp_ty[1] = { 4u };
    int8_t road_vy;
    int8_t sand_vy;

    /* Road baseline — gear 1 (max_speed=4) prevents gear-cap from collapsing
     * road_vy=-3 and sand_vy=-2 to the same clamped value. */
    track_test_set_map(road_map, 8u, 8u);
    racer_spawn_for_test(0, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_E, 1u);
    racer_set_gear_for_test(0u, 1u);
    racer_set_vel_for_test(0u, 0, -4);
    racer_update();
    road_vy = racer_get_vy(0u);

    /* Sand: same start state */
    track_test_set_map(sand_map, 8u, 8u);
    racer_spawn_for_test(0, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_E, 1u);
    racer_set_gear_for_test(0u, 1u);
    racer_set_vel_for_test(0u, 0, -4);
    racer_update();
    sand_vy = racer_get_vy(0u);

    TEST_ASSERT_GREATER_THAN_INT8(road_vy, sand_vy);
}

void test_racer_oil_resets_gear(void) {
    /* All-oil map (tile 12). Racer at gear=2 enters oil: gear must reset to 0. */
    static const uint8_t oil_map[8u * 8u] = {
        12,12,12,12,12,12,12,12,
        12,12,12,12,12,12,12,12,
        12,12,12,12,12,12,12,12,
        12,12,12,12,12,12,12,12,
        12,12,12,12,12,12,12,12,
        12,12,12,12,12,12,12,12,
        12,12,12,12,12,12,12,12,
        12,12,12,12,12,12,12,12,
    };
    uint8_t wp_tx[1] = { 7u };
    uint8_t wp_ty[1] = { 4u };
    track_test_set_map(oil_map, 8u, 8u);
    racer_spawn_for_test(0, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_E, 1u);
    racer_set_gear_for_test(0u, 2u);
    racer_update();
    TEST_ASSERT_EQUAL_UINT8(0u, racer_get_gear(0u));
}

void test_racer_boost_accelerates_upward(void) {
    /* All-boost map (tile 15). Racer heading north with vy=0. After 1 frame vy < 0. */
    static const uint8_t boost_map[8u * 8u] = {
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(boost_map, 8u, 8u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_update();
    TEST_ASSERT_LESS_THAN_INT8(0, racer_get_vy(0u));
}

void test_racer_boost_overrides_gear_max_speed(void) {
    /* All-boost map. Seed vy near gear3 max; after 1 frame vy must exceed
     * RACER_GEAR3_MAX_SPEED in magnitude (boost max cap = TERRAIN_BOOST_MAX_SPEED = 8). */
    static const uint8_t boost_map[8u * 8u] = {
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
        15,15,15,15,15,15,15,15,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(boost_map, 8u, 8u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_set_vel_for_test(0u, 0, -(int8_t)(RACER_GEAR3_MAX_SPEED - 1u));
    racer_update();
    TEST_ASSERT_LESS_THAN_INT8(-(int8_t)RACER_GEAR3_MAX_SPEED, racer_get_vy(0u));
}

void test_racer_terrain_query_uses_top_center(void) {
    /* Mixed map: tile (0,0) = ROAD, tile (1,0) = SAND.
     * Racer at px=0 -> top-left (0,0)=ROAD, top-center (8,0)=SAND.
     * Waypoint far south -> DIR_S (DX=0, DY=1).
     * Inject vx=2 (perpendicular lateral velocity).
     *
     * On ROAD: fric_x = PLAYER_FRICTION     = 1 -> vx: 2->1
     * On SAND: fric_x = PLAYER_FRICTION * 2 = 2 -> vx: 2->0
     *
     * Passes only with top-center query (SAND detected). */
    static const uint8_t mixed_map[4u * 4u] = {
        1, 9, 1, 1,   /* row 0: road, SAND at (1,0), road, road */
        1, 1, 1, 1,
        1, 1, 1, 1,
        1, 1, 1, 1,
    };
    uint8_t wp_tx[1] = { 0u };
    uint8_t wp_ty[1] = { 100u };
    track_test_set_map(mixed_map, 4u, 4u);
    racer_spawn_for_test(0, 0, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 1u);
    racer_set_vel_for_test(0u, 2, 0);
    racer_update();
    TEST_ASSERT_EQUAL_INT8(0, racer_get_vx(0u));
}

/* ---- racer_blocks_pixel ---- */

void test_racer_blocks_pixel_inside(void) {
    /* Racer at (32,32): bbox [32..47]×[32..47]. Centre pixel (40,40) → inside. */
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, racer_blocks_pixel(40, 40));
}

void test_racer_blocks_pixel_boundary(void) {
    /* px+15=47, py+15=47 are the last valid pixels inside the bbox. */
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, racer_blocks_pixel(47, 47));
}

void test_racer_blocks_pixel_outside(void) {
    /* wx=48: 48 < 32+16=48 is FALSE → outside. */
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    TEST_ASSERT_EQUAL_UINT8(0u, racer_blocks_pixel(48, 32));
}

void test_racer_blocks_pixel_inactive(void) {
    /* setUp called racer_init_empty() — no active racer. */
    TEST_ASSERT_EQUAL_UINT8(0u, racer_blocks_pixel(32, 32));
}

/* ---- racer_overlaps_player ---- */

void test_racer_overlaps_player_when_overlapping(void) {
    /* Racer at (32,32): bbox [32..47]×[32..47].
     * Player at (40,40): bbox [40..55]×[40..55].
     * Overlap region [40..47]×[40..47] — must return 1. */
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, racer_overlaps_player(40, 40));
}

void test_racer_overlaps_player_when_adjacent(void) {
    /* Racer at (32,32), player at (48,32).
     * Player bbox starts at 48; racer bbox ends at 47.
     * Condition: px(48) < racer_px(32)+16=48 → FALSE. No overlap. */
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    TEST_ASSERT_EQUAL_UINT8(0u, racer_overlaps_player(48, 32));
}

void test_racer_overlaps_player_when_inactive(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, racer_overlaps_player(32, 32));
}

void test_racer_hp_initialized_to_racer_hp(void) {
    /* racer_init_empty() called in setUp; HP must equal RACER_HP */
    TEST_ASSERT_EQUAL_UINT8(RACER_HP, racer_get_hp_for_test(0u));
}

void test_racer_hit_flash_initialized_to_zero(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, racer_get_hit_flash_for_test(0u));
}

void test_racer_bullet_hit_reduces_hp(void) {
    /* cam_y=0 (setUp). Racer at world (32,32).
     * Screen-space OAM center = (32+16, 32+24) = (48, 56).
     * Fire player bullet at (48,56). racer_update() must decrement HP by 1. */
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(flat_map, 8u, 8u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_set_hp_for_test(0u, RACER_HP);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();
    TEST_ASSERT_EQUAL_UINT8(RACER_HP - 1u, racer_get_hp_for_test(0u));
}

void test_racer_destroyed_when_hp_reaches_zero(void) {
    /* Racer at HP=1. One bullet hit deactivates it. */
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(flat_map, 8u, 8u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_set_hp_for_test(0u, 1u);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();
    TEST_ASSERT_EQUAL_UINT8(0u, racer_active[0]);
}

void test_racer_dead_does_not_trigger_game_over(void) {
    /* Racer killed by bullet. Subsequent racer_update must return 0 (no game over). */
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(flat_map, 8u, 8u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_set_hp_for_test(0u, 1u);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();              /* kills racer */
    TEST_ASSERT_EQUAL_UINT8(0u, racer_update()); /* no game over after death */
}

void test_racer_miss_does_not_reduce_hp(void) {
    /* Bullet fired far from racer — HP must not change. */
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(flat_map, 8u, 8u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    projectile_fire(8u, 16u, DIR_T, PROJ_OWNER_PLAYER); /* top-left corner, far from racer */
    racer_update();
    TEST_ASSERT_EQUAL_UINT8(RACER_HP, racer_get_hp_for_test(0u));
}

void test_racer_get_cp_next_initial_zero(void) {
    uint8_t wp_tx[1] = { 10u };
    uint8_t wp_ty[1] = { 10u };
    racer_spawn_for_test(80, 80, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 3u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

void test_racer_spawn_resets_cp_next(void) {
    uint8_t wp_tx[1] = { 10u };
    uint8_t wp_ty[1] = { 10u };
    race_state_set_cp_for_test(0u, 5u);  /* pre-pollute */
    racer_spawn_for_test(80, 80, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 3u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

void test_racer_get_px_returns_spawn_value(void) {
    uint8_t wp_tx[1] = { 10u };
    uint8_t wp_ty[1] = { 10u };
    racer_spawn_for_test(100, 200, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 3u);
    TEST_ASSERT_EQUAL_INT16(100, racer_get_px(0u));
}

/* ---- Checkpoint update tests ---- */

/* Shared setup helper for checkpoint tests */
static void setup_one_checkpoint_south(CheckpointDef *defs) {
    defs[0].x = 96;  defs[0].y = 400; defs[0].w = 40; defs[0].h = 16;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
}

/* AC1: racer_cp_next increments when inside AABB with matching direction */
void test_racer_cp_next_increments_on_matching_dir(void) {
    CheckpointDef defs[1];
    setup_one_checkpoint_south(defs);
    uint8_t wp_tx[1] = { 10u }, wp_ty[1] = { 10u };
    racer_spawn_for_test(110, 408, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    race_state_update_cp(0u, 110, 408, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));
}

/* AC2: racer_cp_next does NOT increment with wrong direction */
void test_racer_cp_next_no_increment_wrong_dir(void) {
    CheckpointDef defs[1];
    setup_one_checkpoint_south(defs);
    uint8_t wp_tx[1] = { 10u }, wp_ty[1] = { 10u };
    racer_spawn_for_test(110, 408, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 3u);
    race_state_update_cp(0u, 110, 408, DIR_T);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

/* AC3: waypoint wrap does NOT reset cp_next — only race_state_advance_lap resets it */
void test_racer_wp_wrap_does_not_reset_cp(void) {
    CheckpointDef defs[1];
    track_test_set_checkpoints(defs, 0u);
    uint8_t wp_tx[1] = { 10u }, wp_ty[1] = { 10u };
    racer_spawn_for_test(80, 80, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 3u);
    race_state_set_cp_for_test(0u, 2u);
    racer_set_wp_idx_for_test(0u, 0u);
    racer_set_pos_for_test(0u, 80, 80);
    static const uint8_t flat[16*16] = {0};
    track_test_set_map(flat, 16u, 16u);
    racer_update();
    TEST_ASSERT_EQUAL_UINT8(2u, race_state_get_cp(0u));  /* unchanged by wp wrap */
}

/* AC4: sequential enforcement — cp[1] AABB cannot clear before cp[0] */
void test_racer_cp_next_sequential_order_enforced(void) {
    CheckpointDef defs[2];
    defs[0].x = 200; defs[0].y = 200; defs[0].w = 8;  defs[0].h = 8;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    defs[1].x = 96;  defs[1].y = 400; defs[1].w = 40; defs[1].h = 16;
    defs[1].index = 1u; defs[1].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 2u);
    uint8_t wp_tx[1] = { 10u }, wp_ty[1] = { 10u };
    racer_spawn_for_test(110, 408, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    /* Try to clear cp[1] (at 96,400) while cp[0] (at 200,200) not cleared */
    race_state_update_cp(0u, 110, 408, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_racer_inactive_after_init_empty);
    RUN_TEST(test_racer_advances_waypoint_when_close);
    RUN_TEST(test_racer_finish_triggers_game_over);
    RUN_TEST(test_racer_finish_wrong_direction_no_game_over);
    RUN_TEST(test_racer_wraps_waypoints);
    RUN_TEST(test_racer_no_finish_before_all_laps_done);
    RUN_TEST(test_racer_finishes_after_all_laps_done);
    RUN_TEST(test_racer_active_exported_as_global);
    RUN_TEST(test_racer_4corner_blocks_when_corner_hits_wall);
    RUN_TEST(test_racer_slides_along_wall_on_y_collision);
    RUN_TEST(test_racer_accelerates_from_rest);
    RUN_TEST(test_racer_wall_collision_zeroes_vx_and_gear);
    RUN_TEST(test_racer_sand_doubles_friction);
    RUN_TEST(test_racer_oil_resets_gear);
    RUN_TEST(test_racer_boost_accelerates_upward);
    RUN_TEST(test_racer_boost_overrides_gear_max_speed);
    RUN_TEST(test_racer_terrain_query_uses_top_center);
    RUN_TEST(test_racer_blocks_pixel_inside);
    RUN_TEST(test_racer_blocks_pixel_boundary);
    RUN_TEST(test_racer_blocks_pixel_outside);
    RUN_TEST(test_racer_blocks_pixel_inactive);
    RUN_TEST(test_racer_overlaps_player_when_overlapping);
    RUN_TEST(test_racer_overlaps_player_when_adjacent);
    RUN_TEST(test_racer_overlaps_player_when_inactive);
    RUN_TEST(test_racer_hp_initialized_to_racer_hp);
    RUN_TEST(test_racer_hit_flash_initialized_to_zero);
    RUN_TEST(test_racer_bullet_hit_reduces_hp);
    RUN_TEST(test_racer_destroyed_when_hp_reaches_zero);
    RUN_TEST(test_racer_dead_does_not_trigger_game_over);
    RUN_TEST(test_racer_miss_does_not_reduce_hp);
    RUN_TEST(test_racer_get_cp_next_initial_zero);
    RUN_TEST(test_racer_spawn_resets_cp_next);
    RUN_TEST(test_racer_get_px_returns_spawn_value);
    RUN_TEST(test_racer_cp_next_increments_on_matching_dir);
    RUN_TEST(test_racer_cp_next_no_increment_wrong_dir);
    RUN_TEST(test_racer_wp_wrap_does_not_reset_cp);
    RUN_TEST(test_racer_cp_next_sequential_order_enforced);
    return UNITY_END();
}
