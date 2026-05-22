/* tests/test_racer.c */
#include "unity.h"
#include "racer.h"
#include "config.h"
#include "track.h"
#include "checkpoint.h"
#include "player.h"    /* player_dir_t: DIR_T, DIR_B, etc. */

extern int16_t cam_y;

void setUp(void) {
    cam_y = 0;
    racer_init_empty();
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
        1,1,1,1,1,12,1,1, /* row 6: tile 12=TILE_FINISH at col 5 */
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
        1,1,1,1,1,12,1,1,
        1,1,1,1,1,1,1,1,
    };
    /* Waypoint directly north of finish at tile (5,0): delta dx=0, dy<0 → DIR_T */
    uint8_t wp_tx[1] = { 5u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(finish_map, 8u, 8u);
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 1u);
    /* Place racer centre at tile (5,6) = pixel (44,52), heading toward waypoint (5,0) */
    racer_set_pos_for_test(0u, 44, 52);
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
        1,1,1,1,1,12,1,1,
        1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 5u };
    uint8_t wp_ty[1] = { 5u };
    track_test_set_map(finish_map, 8u, 8u);
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    racer_set_laps_done_for_test(2u);  /* 2 of 3 laps done */
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
        1,1,1,1,1,12,1,1,
        1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 5u };
    uint8_t wp_ty[1] = { 5u };
    track_test_set_map(finish_map, 8u, 8u);
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    /* racer_spawn_for_test sets s_laps_done = lap_total = 3 */
    racer_place_on_finish_for_test(5u, 6u, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, racer_update());
}

void test_racer_active_exported_as_global(void) {
    extern uint8_t racer_active[];
    racer_init_empty();
    TEST_ASSERT_EQUAL_UINT8(0u, racer_active[0]);
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
    return UNITY_END();
}
