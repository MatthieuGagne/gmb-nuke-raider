#include "unity.h"
#include <gb/gb.h>          /* mock_vram, mock_vram_clear — tests/mocks/gb/gb.h */
#include "beam.h"
#include "track.h"
#include "camera.h"
#include "config.h"
#include "player.h"

/* 20x16 all-road map. Tile 1 = road (fully passable), tile 0 = wall (fully solid).
 * NO 2-byte header: track_test_set_map() takes raw tile data. */
static uint8_t s_map[20 * 16];
static const uint8_t k_open[8]  = {0xFFu,0xFFu,0xFFu,0xFFu,0xFFu,0xFFu,0xFFu,0xFFu};
static const uint8_t k_solid[8] = {0x00u,0x00u,0x00u,0x00u,0x00u,0x00u,0x00u,0x00u};

static void map_all_road(void) {
    uint16_t i;
    for (i = 0u; i < 20u * 16u; i++) s_map[i] = 1u;
    track_test_set_map(s_map, 20u, 16u);
    track_test_set_collision_mask(1u, k_open);
    track_test_set_collision_mask(0u, k_solid);
}

static void map_wall_at(uint8_t tx, uint8_t ty) {
    s_map[(uint16_t)ty * 20u + tx] = 0u;
}

void setUp(void) {
    map_all_road();
    camera_set_tile_base(0u);
    camera_init(0, 0);       /* 20x16 map -> cam_x = cam_y = 0, both clamped */
    camera_flush_vram();
    beam_init(0x40u);        /* BG tile base; asserted in the render tests */
    beam_set_equipped(1u);
}
void tearDown(void) {}

/* Geometry every case relies on: a car top-left at (64,64) has centre (72,72)
 * = tile (9,9). Firing right, the raycast starts at cx+8 = 80 = tile 10, so the
 * car's own tile 9 is never painted. The damage band is cy +/- BEAM_LANE_HALF
 * = 68..76. */

void test_diagonal_press_does_not_fire(void) {
    TEST_ASSERT_EQUAL_UINT8(0, beam_fire(64, 64, DIR_RT));
    TEST_ASSERT_EQUAL_UINT8(0, beam_fire(64, 64, DIR_RB));
    TEST_ASSERT_EQUAL_UINT8(0, beam_fire(64, 64, DIR_LB));
    TEST_ASSERT_EQUAL_UINT8(0, beam_fire(64, 64, DIR_LT));
}

void test_diagonal_press_deals_no_damage(void) {
    (void)beam_fire(64, 64, DIR_RT);
    TEST_ASSERT_EQUAL_UINT8(0, beam_hit_damage(96, 64, 16u));
}

void test_diagonal_press_does_not_consume_the_cooldown(void) {
    (void)beam_fire(64, 64, DIR_RT);
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
}

void test_all_four_cardinals_fire(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));  beam_reset();
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_L));  beam_reset();
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_T));  beam_reset();
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_B));
}

void test_pierce_damages_every_enemy_in_the_lane(void) {
    /* Open lane: cells tile 10..19, so the rect is world x 80..160. */
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_LASER_DAMAGE, beam_hit_damage(96, 64, 16u));
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_LASER_DAMAGE, beam_hit_damage(128, 64, 16u));
}

void test_wall_blocks_everything_behind_it(void) {
    /* Wall at tile x 14 (world 112-119) -> cells 10..13, rect x 80..112. */
    map_wall_at(14u, 9u);
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_LASER_DAMAGE, beam_hit_damage(96, 64, 16u));
    TEST_ASSERT_EQUAL_UINT8(0, beam_hit_damage(128, 64, 16u));
}

void test_enemy_outside_the_lane_is_missed(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    TEST_ASSERT_EQUAL_UINT8(0, beam_hit_damage(96, 96, 16u));
}

void test_enemy_behind_the_car_is_missed(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    TEST_ASSERT_EQUAL_UINT8(0, beam_hit_damage(16, 64, 16u));
}

void test_turret_sized_box_is_hittable(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_LASER_DAMAGE, beam_hit_damage(96, 72, 8u));
}

void test_left_beam_damages_enemies_left_of_the_car(void) {
    /* DIR_L: cells tile 8 down to 0, rect x 0..72. */
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_L));
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_LASER_DAMAGE, beam_hit_damage(16, 64, 16u));
    TEST_ASSERT_EQUAL_UINT8(0, beam_hit_damage(96, 64, 16u));
}

void test_vertical_beam_pierces_downward(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 32, DIR_B));
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_LASER_DAMAGE, beam_hit_damage(64, 64, 16u));
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_LASER_DAMAGE, beam_hit_damage(64, 96, 16u));
}

void test_damage_window_closes_after_one_update(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_LASER_DAMAGE, beam_hit_damage(96, 64, 16u));
    beam_update(64, 64);
    TEST_ASSERT_EQUAL_UINT8(0, beam_hit_damage(96, 64, 16u));
}

void test_cadence_is_laser_fire_cooldown(void) {
    uint8_t i;
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    for (i = 0u; i < (uint8_t)(LASER_FIRE_COOLDOWN - 1u); i++) {
        beam_update(64, 64);
        TEST_ASSERT_EQUAL_UINT8(0, beam_fire(64, 64, DIR_R));
    }
    beam_update(64, 64);
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
}

void test_cadence_is_slower_than_cannon(void) {
    uint8_t i;
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    for (i = 0u; i < (uint8_t)PROJ_FIRE_COOLDOWN; i++) beam_update(64, 64);
    TEST_ASSERT_EQUAL_UINT8(0, beam_fire(64, 64, DIR_R));
}

void test_cannon_loadout_never_fires_a_beam(void) {
    beam_set_equipped(0u);
    TEST_ASSERT_EQUAL_UINT8(0, beam_is_equipped());
    TEST_ASSERT_EQUAL_UINT8(0, beam_fire(64, 64, DIR_R));
}

void test_render_draws_the_whole_lane(void) {
    uint8_t tx;
    map_wall_at(14u, 9u);
    mock_vram_clear();
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    beam_render();
    for (tx = 10u; tx <= 13u; tx++) {
        TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + tx]);
    }
    /* The car's own tile is deliberately unpainted. */
    TEST_ASSERT_NOT_EQUAL(0x40u, mock_vram[(9u * 32u) + 9u]);
    TEST_ASSERT_NOT_EQUAL(0x40u, mock_vram[(9u * 32u) + 14u]);
}

void test_left_beam_paints_the_cells_left_of_the_car(void) {
    /* set_bkg_tiles writes ASCENDING, but DIR_L sweeps descending. The cell
     * origin must be the LOWEST tile of the span (0), not the first probed (8). */
    uint8_t tx;
    mock_vram_clear();
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_L));
    beam_render();
    for (tx = 0u; tx <= 8u; tx++) {
        TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + tx]);
    }
    TEST_ASSERT_NOT_EQUAL(0x40u, mock_vram[(9u * 32u) + 10u]);
}

void test_up_beam_paints_the_cells_above_the_car(void) {
    /* DIR_T from (64,64): rows 8 down to 0 at column 9, vertical tile 0x41. */
    uint8_t ty;
    mock_vram_clear();
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_T));
    beam_render();
    for (ty = 0u; ty <= 8u; ty++) {
        TEST_ASSERT_EQUAL_UINT8(0x41u, mock_vram[(ty * 32u) + 9u]);
    }
    TEST_ASSERT_NOT_EQUAL(0x41u, mock_vram[(10u * 32u) + 9u]);
}

void test_render_draws_nothing_once_the_pulse_expires(void) {
    uint8_t i;
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    for (i = 0u; i < (uint8_t)BEAM_VISIBLE_FRAMES; i++) beam_update(64, 64);
    mock_vram_clear();
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0, mock_vram[(9u * 32u) + 10u]);
}

void test_expiry_queues_the_restore(void) {
    uint8_t i;
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 10u]);
    for (i = 0u; i < (uint8_t)BEAM_VISIBLE_FRAMES; i++) beam_update(64, 64);
    camera_flush_vram();
    TEST_ASSERT_NOT_EQUAL(0x40u, mock_vram[(9u * 32u) + 10u]);
}

void test_vertical_expiry_queues_the_column_restore(void) {
    uint8_t i;
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 32, DIR_B));
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x41u, mock_vram[(8u * 32u) + 9u]);
    for (i = 0u; i < (uint8_t)BEAM_VISIBLE_FRAMES; i++) beam_update(64, 32);
    camera_flush_vram();
    TEST_ASSERT_NOT_EQUAL(0x41u, mock_vram[(8u * 32u) + 9u]);
}

/* ---- per-frame start and length (#582) -------------------------------- */

/* Geometry: the car top-left at (64,64) has centre (72,72); firing right, the
 * nose pixel is 80 = tile 10. Advancing the car to (72,64) moves the nose to
 * 88 = tile 11. The all-road map is 20 tiles wide, so the lane runs to tile 19
 * (world x 152..159), where the 160 px screen clip ends.
 *
 * "No longer covered" is asserted as NOT_EQUAL against the beam tile, never as
 * EQUAL against 0: Task 3 repaints those cells with the track tile, and an
 * EQUAL-0 assertion would turn green here and red one task later. */

void test_start_follows_the_car_nose(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    beam_render();
    beam_update(72, 64);              /* the car advanced one tile along the lane */
    mock_vram_clear();
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 11u]);
    TEST_ASSERT_NOT_EQUAL(0x40u,     mock_vram[(9u * 32u) + 10u]);
}

void test_start_never_moves_backwards(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    beam_render();
    beam_update(72, 64);              /* forward: the start reaches tile 11 */
    beam_update(56, 64);              /* the car reverses: the start stays at 11 */
    mock_vram_clear();
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 11u]);
    TEST_ASSERT_NOT_EQUAL(0x40u,     mock_vram[(9u * 32u) + 10u]);
}

/* Regression guard, not a red test: today's frozen lane also paints row 9 only.
 * Its input flip is the implementation — make s_lane_px track py instead of
 * holding the fire-frame value and row 13 gets painted. */
void test_lane_row_is_fixed_while_the_car_drifts(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    beam_render();
    beam_update(72, 96);              /* the car drifts 32 px down during the pulse */
    mock_vram_clear();
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u)  + 11u]);   /* the fire row */
    TEST_ASSERT_NOT_EQUAL(0x40u,     mock_vram[(13u * 32u) + 11u]); /* the car's new row */
}

void test_length_still_stops_at_the_wall_as_the_start_advances(void) {
    map_wall_at(14u, 9u);
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));   /* cells 10..13 */
    beam_render();
    beam_update(72, 64);                                    /* cells 11..13 */
    mock_vram_clear();
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 13u]);
    TEST_ASSERT_NOT_EQUAL(0x40u,     mock_vram[(9u * 32u) + 14u]);
    TEST_ASSERT_NOT_EQUAL(0x40u,     mock_vram[(9u * 32u) + 10u]);
}

void test_no_free_cell_in_front_draws_nothing(void) {
    map_wall_at(14u, 9u);
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));   /* cells 10..13 */
    beam_render();
    beam_update(96, 64);              /* the nose pixel is 112 — inside the wall tile */
    mock_vram_clear();
    beam_render();
    TEST_ASSERT_NOT_EQUAL(0x40u, mock_vram[(9u * 32u) + 13u]);
    TEST_ASSERT_NOT_EQUAL(0x40u, mock_vram[(9u * 32u) + 14u]);
}

/* AC6: one pulse, one damage window — while the car drives forward through the
 * whole cadence. Two pulses fire in LASER_FIRE_COOLDOWN + 2 frames, so the
 * count is 2. A start that re-applied damage as it moved would count more. */
void test_each_pulse_damages_once_while_the_car_moves(void) {
    uint8_t i;
    uint8_t windows = 0u;
    int16_t px = 64;
    for (i = 0u; i < (uint8_t)(LASER_FIRE_COOLDOWN + 2u); i++) {
        (void)beam_fire(px, 64, DIR_R);              /* refused while on cooldown */
        if (beam_hit_damage(96, 64, 16u)) windows++;
        beam_update(px, 64);
        px = (int16_t)(px + 1);                      /* the car keeps driving */
    }
    TEST_ASSERT_EQUAL_UINT8(2, windows);
}

/* AC7: the flash lasts as many frames as it does today. beam_fire() is followed
 * by the fire frame's own beam_update(), exactly as state_playing.c orders them,
 * so the pulse paints on BEAM_VISIBLE_FRAMES - 1 frames. */
void test_the_flash_lasts_the_same_number_of_frames(void) {
    uint8_t i;
    uint8_t painted = 0u;
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));
    beam_update(64, 64);
    for (i = 0u; i < (uint8_t)(BEAM_VISIBLE_FRAMES + 3u); i++) {
        mock_vram_clear();
        beam_render();
        if (mock_vram[(9u * 32u) + 10u] == 0x40u) painted++;
        beam_update(64, 64);
    }
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(BEAM_VISIBLE_FRAMES - 1u), painted);
}

/* ---- incremental repair (#582) ---------------------------------------- */

/* The test map is all road, tile 1, and the camera tile base is 0, so a
 * repaired cell reads back as 1 while a beam cell reads 0x40 or 0x41. */

void test_a_cell_the_beam_leaves_shows_its_track_tile_again(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));   /* cells 10..19 */
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 10u]);
    beam_update(72, 64);                                    /* cells 11..19 */
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(1u,    mock_vram[(9u * 32u) + 10u]);
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 11u]);
}

void test_a_vertical_beam_repairs_the_cell_it_leaves(void) {
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 32, DIR_B));   /* column 9, rows 6..15 */
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x41u, mock_vram[(6u * 32u) + 9u]);
    beam_update(64, 40);                                    /* the car advanced one tile */
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(1u,    mock_vram[(6u * 32u) + 9u]);
    TEST_ASSERT_EQUAL_UINT8(0x41u, mock_vram[(7u * 32u) + 9u]);
}

void test_a_zero_cell_frame_clears_the_whole_painted_span(void) {
    map_wall_at(14u, 9u);
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));   /* cells 10..13 */
    beam_render();
    beam_update(96, 64);              /* the nose pixel is 112 — inside the wall tile */
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(1u, mock_vram[(9u * 32u) + 10u]);
    TEST_ASSERT_EQUAL_UINT8(1u, mock_vram[(9u * 32u) + 13u]);
}

void test_a_long_jump_defers_to_the_whole_lane_repair(void) {
    /* Seven cells leave in one frame — more than CAMERA_REPAIR_MAX_CELLS. The
     * car cannot do this at 6 px per frame; the fallback exists so no cell is
     * left stale for the rest of the pulse. beam_render() only raises the flag:
     * the queueing itself must happen in beam_update(), after camera_update(),
     * or the camera drops its own scroll stream (src/camera.h:53). */
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));   /* cells 10..19 */
    beam_render();
    beam_update(120, 64);                                   /* cells 17..19 */
    beam_render();                                          /* raises the flag */
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 10u]);   /* still stale */
    beam_update(120, 64);                                   /* queues the lane */
    camera_flush_vram();                                    /* drains it */
    TEST_ASSERT_EQUAL_UINT8(1u,    mock_vram[(9u * 32u) + 10u]);
}

/* The beam_cast() memo is keyed on (nose, vis_lo, vis_hi) and deliberately not
 * on s_step, so a new pulse MUST invalidate it. These two pulses share a key
 * and run in opposite directions: without the reset in beam_fire(), the second
 * one reuses the first one's span. beam_reset() would also clear the memo and
 * would hide the bug, so the cooldown is drained with beam_update() instead. */
void test_a_new_pulse_recasts_when_only_the_direction_flips(void) {
    uint8_t i;
    map_wall_at(4u, 9u);                                     /* stops the leftward beam */
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));    /* cells 10..19 */
    for (i = 0u; i < (uint8_t)LASER_FIRE_COOLDOWN; i++) beam_update(64, 64);
    mock_vram_clear();
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(80, 64, DIR_L));    /* cells 5..10 */
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 5u]);
    TEST_ASSERT_NOT_EQUAL(0x40u,   mock_vram[(9u * 32u) + 4u]);   /* the wall */
    TEST_ASSERT_NOT_EQUAL(0x40u,   mock_vram[(9u * 32u) + 11u]);  /* no stale R span */
}

/* The repair runs from the LOW tile of the span, so for DIR_L and DIR_T — where
 * the car chases the beam toward a lower tile index — the cell the beam leaves
 * is at the HIGH end of the span. That is a different arm of the run
 * arithmetic than DIR_R and DIR_B use, and these two tests are what execute it. */

void test_a_left_beam_repairs_the_cell_it_leaves(void) {
    /* DIR_L from (64,64): centre 72, nose 64 -> cells 8..0 on row 9.
     * The car moves one tile left: nose 56 -> cells 7..0, so tile 8 leaves. */
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_L));
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 8u]);
    beam_update(56, 64);
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(1u,    mock_vram[(9u * 32u) + 8u]);
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 7u]);
}

void test_an_up_beam_repairs_the_cell_it_leaves(void) {
    /* DIR_T from (64,64): centre 72, nose 64 -> rows 8..0 on column 9.
     * The car moves one tile up: nose 56 -> rows 7..0, so row 8 leaves. */
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_T));
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x41u, mock_vram[(8u * 32u) + 9u]);
    beam_update(64, 56);
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(1u,    mock_vram[(8u * 32u) + 9u]);
    TEST_ASSERT_EQUAL_UINT8(0x41u, mock_vram[(7u * 32u) + 9u]);
}

/* A pulse longer than CAMERA_REPAIR_MAX_CELLS that loses its last free cell
 * takes the whole-lane fallback, which lands one frame later. This pins that
 * lag so it stays deliberate: the existing zero-cell test uses a 4-cell span,
 * which sits exactly on the cap and never reaches this path. */
void test_a_long_pulse_that_dies_on_a_wall_repairs_one_frame_later(void) {
    map_wall_at(16u, 9u);
    TEST_ASSERT_EQUAL_UINT8(1, beam_fire(64, 64, DIR_R));   /* cells 10..15 */
    beam_render();
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 10u]);
    beam_update(112, 64);            /* the nose pixel is 128 — inside the wall tile */
    beam_render();                   /* 6 cells leave at once: the fallback is raised */
    TEST_ASSERT_EQUAL_UINT8(0x40u, mock_vram[(9u * 32u) + 10u]);   /* still stale */
    beam_update(112, 64);            /* queues the lane, after camera_update() */
    camera_flush_vram();             /* drains it */
    TEST_ASSERT_EQUAL_UINT8(1u,     mock_vram[(9u * 32u) + 10u]);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_diagonal_press_does_not_fire);
    RUN_TEST(test_diagonal_press_deals_no_damage);
    RUN_TEST(test_diagonal_press_does_not_consume_the_cooldown);
    RUN_TEST(test_all_four_cardinals_fire);
    RUN_TEST(test_pierce_damages_every_enemy_in_the_lane);
    RUN_TEST(test_wall_blocks_everything_behind_it);
    RUN_TEST(test_enemy_outside_the_lane_is_missed);
    RUN_TEST(test_enemy_behind_the_car_is_missed);
    RUN_TEST(test_turret_sized_box_is_hittable);
    RUN_TEST(test_left_beam_damages_enemies_left_of_the_car);
    RUN_TEST(test_vertical_beam_pierces_downward);
    RUN_TEST(test_damage_window_closes_after_one_update);
    RUN_TEST(test_cadence_is_laser_fire_cooldown);
    RUN_TEST(test_cadence_is_slower_than_cannon);
    RUN_TEST(test_cannon_loadout_never_fires_a_beam);
    RUN_TEST(test_render_draws_the_whole_lane);
    RUN_TEST(test_left_beam_paints_the_cells_left_of_the_car);
    RUN_TEST(test_up_beam_paints_the_cells_above_the_car);
    RUN_TEST(test_render_draws_nothing_once_the_pulse_expires);
    RUN_TEST(test_expiry_queues_the_restore);
    RUN_TEST(test_vertical_expiry_queues_the_column_restore);
    RUN_TEST(test_start_follows_the_car_nose);
    RUN_TEST(test_start_never_moves_backwards);
    RUN_TEST(test_lane_row_is_fixed_while_the_car_drifts);
    RUN_TEST(test_length_still_stops_at_the_wall_as_the_start_advances);
    RUN_TEST(test_no_free_cell_in_front_draws_nothing);
    RUN_TEST(test_each_pulse_damages_once_while_the_car_moves);
    RUN_TEST(test_the_flash_lasts_the_same_number_of_frames);
    RUN_TEST(test_a_cell_the_beam_leaves_shows_its_track_tile_again);
    RUN_TEST(test_a_vertical_beam_repairs_the_cell_it_leaves);
    RUN_TEST(test_a_zero_cell_frame_clears_the_whole_painted_span);
    RUN_TEST(test_a_long_jump_defers_to_the_whole_lane_repair);
    RUN_TEST(test_a_new_pulse_recasts_when_only_the_direction_flips);
    RUN_TEST(test_a_left_beam_repairs_the_cell_it_leaves);
    RUN_TEST(test_an_up_beam_repairs_the_cell_it_leaves);
    RUN_TEST(test_a_long_pulse_that_dies_on_a_wall_repairs_one_frame_later);
    return UNITY_END();
}
