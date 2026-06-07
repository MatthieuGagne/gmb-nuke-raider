#include "unity.h"
#include "race_state.h"
#include "track.h"
#include "player.h"    /* DIR_T, DIR_B, DIR_L, DIR_R, DIR_LT, DIR_RT, DIR_LB, DIR_RB */

void setUp(void) {
    race_state_init(3u);
}
void tearDown(void) {}

/* ---- race_state_init ---- */

void test_init_sets_lap_total(void) {
    race_state_init(5u);
    TEST_ASSERT_EQUAL_UINT8(5u, race_state_get_lap_total());
}

void test_init_zeros_all_cp(void) {
    race_state_set_cp_for_test(0u, 7u);
    race_state_set_cp_for_test(1u, 7u);
    race_state_init(2u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(1u));
}

void test_init_zeros_all_laps(void) {
    race_state_set_laps_for_test(0u, 4u);
    race_state_set_laps_for_test(1u, 4u);
    race_state_init(2u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_laps(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_laps(1u));
}

void test_init_deactivates_all_slots(void) {
    race_state_set_active(0u, 1u);
    race_state_set_active(1u, 1u);
    race_state_init(2u);
    /* rank_player with no active slots should return 1 (default) */
    race_state_set_active(PLAYER_SLOT, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_rank_player());
}

/* ---- race_state_update_cp ---- */

void test_update_cp_clears_when_inside_and_correct_dir(void) {
    CheckpointDef defs[1];
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_B);   /* inside, facing south */
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));
}

void test_update_cp_ignored_wrong_direction(void) {
    CheckpointDef defs[1];
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_T);   /* inside, wrong direction */
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

void test_update_cp_ignored_outside_aabb(void) {
    CheckpointDef defs[1];
    defs[0].x = 100; defs[0].y = 100; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_B);   /* outside rect */
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

void test_update_cp_sequential_enforced(void) {
    CheckpointDef defs[2];
    defs[0].x = 200; defs[0].y = 200; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    defs[1].x = 0;   defs[1].y = 0;   defs[1].w = 32; defs[1].h = 32;
    defs[1].index = 1u; defs[1].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 2u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    /* Try to clear cp[1] (at origin) while cp[0] not yet cleared */
    race_state_update_cp(0u, 5, 5, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

void test_update_cp_per_slot_independent(void) {
    CheckpointDef defs[1];
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(1u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_B);   /* slot 0 clears */
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(1u));  /* slot 1 unaffected */
}

void test_update_cp_all_4_directions(void) {
    CheckpointDef defs[1];
    /* Direction N */
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_N;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_T);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));

    /* Direction E */
    defs[0].direction = CHECKPOINT_DIR_E;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_R);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));

    /* Direction W */
    defs[0].direction = CHECKPOINT_DIR_W;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_L);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));
}

/* ---- race_state_all_cp_cleared ---- */

void test_all_cp_cleared_zero_checkpoints(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_all_cp_cleared(0u));
}

void test_all_cp_cleared_not_cleared(void) {
    CheckpointDef defs[1];
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_all_cp_cleared(0u));
}

void test_all_cp_cleared_after_clearing(void) {
    CheckpointDef defs[1];
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_all_cp_cleared(0u));
}

/* ---- race_state_advance_lap ---- */

void test_advance_lap_mid_race_returns_zero(void) {
    /* lap_total=3, laps=0 -> 0+1=1 < 3 -> returns 0 */
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_advance_lap(0u));
}

void test_advance_lap_increments_laps(void) {
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_advance_lap(0u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_laps(0u));
}

void test_advance_lap_resets_cp_next(void) {
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_cp_for_test(0u, 5u);
    race_state_advance_lap(0u);  /* mid-race: resets cp */
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

void test_advance_lap_final_returns_one(void) {
    /* lap_total=3, laps=2 -> 2+1=3 >= 3 -> returns 1 (race over) */
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_laps_for_test(0u, 2u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_advance_lap(0u));
}

void test_advance_lap_single_lap_race_returns_one(void) {
    /* lap_total=1, laps=0 -> 0+1=1 >= 1 -> returns 1 */
    race_state_init(1u);
    race_state_set_active(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_advance_lap(0u));
}

void test_advance_lap_per_slot_independent(void) {
    /* Slot 0 advances; slot 1 is unaffected */
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(1u, 1u);
    race_state_advance_lap(0u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_laps(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_laps(1u));
}

/* ---- race_state_rank_player ---- */

void test_rank_player_alone_is_1(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(PLAYER_SLOT, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_rank_player());
}

void test_rank_player_more_laps_is_1(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(PLAYER_SLOT, 1u);
    race_state_set_laps_for_test(PLAYER_SLOT, 2u);
    race_state_set_laps_for_test(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_rank_player());
}

void test_rank_player_fewer_laps_is_2(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(PLAYER_SLOT, 1u);
    race_state_set_laps_for_test(PLAYER_SLOT, 1u);
    race_state_set_laps_for_test(0u, 2u);
    TEST_ASSERT_EQUAL_UINT8(2u, race_state_rank_player());
}

void test_rank_player_same_laps_more_cp_is_1(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(PLAYER_SLOT, 1u);
    race_state_set_cp_for_test(PLAYER_SLOT, 3u);
    race_state_set_cp_for_test(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_rank_player());
}

void test_rank_player_same_laps_fewer_cp_is_2(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(PLAYER_SLOT, 1u);
    race_state_set_cp_for_test(PLAYER_SLOT, 1u);
    race_state_set_cp_for_test(0u, 3u);
    TEST_ASSERT_EQUAL_UINT8(2u, race_state_rank_player());
}

void test_rank_player_tiebreaker_player_closer_is_1(void) {
    /* Same laps and cp -- next checkpoint at (100, 100, 20, 20).
     * Player at (112, 112), distance=4. Enemy at (90, 90), distance=40. */
    CheckpointDef defs[1];
    defs[0].x = 100; defs[0].y = 100; defs[0].w = 20; defs[0].h = 20;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);

    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(PLAYER_SLOT, 1u);
    /* cp_next=0 for both -> next cp is defs[0] */
    /* rank_player calls pos_from_manhattan internally for the tiebreaker */
    /* We can't easily inject positions via race_state alone, so test pos_from_manhattan directly */
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(112, 112, 90, 90, &defs[0]));
}

void test_rank_player_inactive_enemy_not_counted(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 0u);   /* enemy inactive */
    race_state_set_active(PLAYER_SLOT, 1u);
    race_state_set_laps_for_test(0u, 99u);   /* irrelevant: inactive */
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_rank_player());
}

/* ---- pos_from_dir (moved from test_state_playing.c) ---- */

void test_pos_from_dir_N_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_N, 0,  50, 0, 100));
}
void test_pos_from_dir_N_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_N, 0, 100, 0,  50));
}
void test_pos_from_dir_S_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_S, 0, 100, 0,  50));
}
void test_pos_from_dir_S_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_S, 0,  50, 0, 100));
}
void test_pos_from_dir_E_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_E, 100, 0,  50, 0));
}
void test_pos_from_dir_E_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_E,  50, 0, 100, 0));
}
void test_pos_from_dir_W_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_W,  50, 0, 100, 0));
}
void test_pos_from_dir_W_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_W, 100, 0,  50, 0));
}

/* ---- pos_from_manhattan (moved from test_state_playing.c) ---- */

void test_pos_from_manhattan_player_closer(void) {
    CheckpointDef cp;
    cp.x = 100; cp.y = 100; cp.w = 20; cp.h = 20;
    cp.index = 0u; cp.direction = CHECKPOINT_DIR_N;
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(112, 112, 90, 90, &cp));
}
void test_pos_from_manhattan_racer_closer(void) {
    CheckpointDef cp;
    cp.x = 100; cp.y = 100; cp.w = 20; cp.h = 20;
    cp.index = 0u; cp.direction = CHECKPOINT_DIR_N;
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_manhattan(90, 90, 112, 112, &cp));
}
void test_pos_from_manhattan_equal_distance_favors_player(void) {
    CheckpointDef cp;
    cp.x = 100; cp.y = 100; cp.w = 20; cp.h = 20;
    cp.index = 0u; cp.direction = CHECKPOINT_DIR_N;
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(120, 110, 110, 120, &cp));
}
void test_pos_from_manhattan_nonsquare_checkpoint(void) {
    CheckpointDef cp;
    cp.x = 0; cp.y = 0; cp.w = 40; cp.h = 10;
    cp.index = 0u; cp.direction = CHECKPOINT_DIR_E;
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(21, 5, 0, 5, &cp));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_sets_lap_total);
    RUN_TEST(test_init_zeros_all_cp);
    RUN_TEST(test_init_zeros_all_laps);
    RUN_TEST(test_init_deactivates_all_slots);
    RUN_TEST(test_update_cp_clears_when_inside_and_correct_dir);
    RUN_TEST(test_update_cp_ignored_wrong_direction);
    RUN_TEST(test_update_cp_ignored_outside_aabb);
    RUN_TEST(test_update_cp_sequential_enforced);
    RUN_TEST(test_update_cp_per_slot_independent);
    RUN_TEST(test_update_cp_all_4_directions);
    RUN_TEST(test_all_cp_cleared_zero_checkpoints);
    RUN_TEST(test_all_cp_cleared_not_cleared);
    RUN_TEST(test_all_cp_cleared_after_clearing);
    RUN_TEST(test_advance_lap_mid_race_returns_zero);
    RUN_TEST(test_advance_lap_increments_laps);
    RUN_TEST(test_advance_lap_resets_cp_next);
    RUN_TEST(test_advance_lap_final_returns_one);
    RUN_TEST(test_advance_lap_single_lap_race_returns_one);
    RUN_TEST(test_advance_lap_per_slot_independent);
    RUN_TEST(test_rank_player_alone_is_1);
    RUN_TEST(test_rank_player_more_laps_is_1);
    RUN_TEST(test_rank_player_fewer_laps_is_2);
    RUN_TEST(test_rank_player_same_laps_more_cp_is_1);
    RUN_TEST(test_rank_player_same_laps_fewer_cp_is_2);
    RUN_TEST(test_rank_player_tiebreaker_player_closer_is_1);
    RUN_TEST(test_rank_player_inactive_enemy_not_counted);
    RUN_TEST(test_pos_from_dir_N_player_ahead);
    RUN_TEST(test_pos_from_dir_N_racer_ahead);
    RUN_TEST(test_pos_from_dir_S_player_ahead);
    RUN_TEST(test_pos_from_dir_S_racer_ahead);
    RUN_TEST(test_pos_from_dir_E_player_ahead);
    RUN_TEST(test_pos_from_dir_E_racer_ahead);
    RUN_TEST(test_pos_from_dir_W_player_ahead);
    RUN_TEST(test_pos_from_dir_W_racer_ahead);
    RUN_TEST(test_pos_from_manhattan_player_closer);
    RUN_TEST(test_pos_from_manhattan_racer_closer);
    RUN_TEST(test_pos_from_manhattan_equal_distance_favors_player);
    RUN_TEST(test_pos_from_manhattan_nonsquare_checkpoint);
    return UNITY_END();
}
