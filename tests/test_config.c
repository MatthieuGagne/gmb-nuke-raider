#include "unity.h"
#include "config.h"
#include "sfx.h"

void setUp(void) {}
void tearDown(void) {}

void test_debug_log_does_not_overlap_tick(void) {
    /* ring buffer occupies [DEBUG_LOG_ADDR, DEBUG_LOG_ADDR + DEBUG_LOG_SIZE) */
    /* LOG_IDX and TICK_ADDR must be outside that range */
    TEST_ASSERT_TRUE(DEBUG_LOG_IDX  >= DEBUG_LOG_ADDR + DEBUG_LOG_SIZE);
    TEST_ASSERT_TRUE(DEBUG_TICK_ADDR >= DEBUG_LOG_ADDR + DEBUG_LOG_SIZE);
    TEST_ASSERT_NOT_EQUAL(DEBUG_LOG_IDX, DEBUG_TICK_ADDR);
}

void test_debug_addresses_in_wram(void) {
    TEST_ASSERT_TRUE(DEBUG_LOG_ADDR  >= 0xC000U);
    TEST_ASSERT_TRUE(DEBUG_TICK_ADDR <= 0xDFFFU);
}

void test_sfx_count_defined(void) {
    TEST_ASSERT_EQUAL_UINT8(4u, SFX_COUNT);
}

void test_max_checkpoints_defined(void) {
    TEST_ASSERT_EQUAL_UINT8(8u, MAX_CHECKPOINTS);
}

void test_enemy_bullet_damage_defined(void) {
    TEST_ASSERT_EQUAL_UINT8(10u, ENEMY_BULLET_DAMAGE);
}

void test_laser_cooldown_distinct_from_cannon(void) {
    /* R5: the beam cadence must be its own tunable, not PROJ_FIRE_COOLDOWN (8). */
    TEST_ASSERT_EQUAL_UINT8(20, LASER_FIRE_COOLDOWN);
    TEST_ASSERT_NOT_EQUAL(PROJ_FIRE_COOLDOWN, LASER_FIRE_COOLDOWN);
}

void test_beam_cells_cover_the_viewport(void) {
    /* A horizontal beam spans at most ceil(160/8)+1 = 21 tile columns; the render
     * buffer must hold that, and camera.c streams 22 (VIS_COLS) for the same reason. */
    TEST_ASSERT_GREATER_OR_EQUAL(21, BEAM_MAX_CELLS);
}

void test_beam_lane_half_matches_the_drawn_tile(void) {
    /* beam_render() paints exactly one 8px tile, so the damage band is +/- 4px
     * around the muzzle centre. A wider band would damage enemies the player
     * never saw the beam touch. */
    TEST_ASSERT_EQUAL_UINT8(4, BEAM_LANE_HALF);
    TEST_ASSERT_EQUAL_UINT8(8, BEAM_LANE_HALF * 2u);
}

void test_laser_is_weapon1_option_one(void) {
    /* LOADOUT_WEAPON1_NAMES[] = {"CANNON", "LASER"} — LASER is index 1. */
    TEST_ASSERT_EQUAL_UINT8(1, LOADOUT_WEAPON1_LASER);
    TEST_ASSERT_LESS_THAN_UINT8(LOADOUT_OPTIONS_PER_FIELD, LOADOUT_WEAPON1_LASER);
}

void test_beam_visible_frames_fit_inside_the_cooldown(void) {
    /* The pulse must finish and restore before the next pulse can fire, or two
     * lanes would be live at once and the restore would target the wrong one. */
    TEST_ASSERT_GREATER_THAN_UINT8(BEAM_VISIBLE_FRAMES, LASER_FIRE_COOLDOWN);
}

void test_beam_segment_tile_offsets_are_distinct(void) {
    /* beam_render() picks one of two tiles off the same asset base. */
    TEST_ASSERT_NOT_EQUAL(BEAM_TILE_OFS_H, BEAM_TILE_OFS_V);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_debug_log_does_not_overlap_tick);
    RUN_TEST(test_debug_addresses_in_wram);
    RUN_TEST(test_sfx_count_defined);
    RUN_TEST(test_max_checkpoints_defined);
    RUN_TEST(test_enemy_bullet_damage_defined);
    RUN_TEST(test_laser_cooldown_distinct_from_cannon);
    RUN_TEST(test_beam_cells_cover_the_viewport);
    RUN_TEST(test_beam_lane_half_matches_the_drawn_tile);
    RUN_TEST(test_laser_is_weapon1_option_one);
    RUN_TEST(test_beam_visible_frames_fit_inside_the_cooldown);
    RUN_TEST(test_beam_segment_tile_offsets_are_distinct);
    return UNITY_END();
}
