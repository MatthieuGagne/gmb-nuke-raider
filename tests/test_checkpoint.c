#include "unity.h"
#include "../src/player.h"
#include "../src/checkpoint.h"

void setUp(void)    {}
void tearDown(void) {}

/* Build a minimal CheckpointDef for tests */
static CheckpointDef make_cp(int16_t x, int16_t y,
                              uint8_t w, uint8_t h,
                              uint8_t index, uint8_t dir) {
    CheckpointDef cp;
    cp.x = x; cp.y = y;
    cp.w = w; cp.h = h;
    cp.index = index; cp.direction = dir;
    return cp;
}

/* 0-checkpoint track: all_cleared() returns 1 immediately */
void test_zero_checkpoints_all_cleared(void) {
    checkpoint_init(NULL, 0u);
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
}

/* 1-checkpoint track: not cleared at init */
void test_one_checkpoint_not_cleared_at_init(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(10, 10, 20, 20, 0u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 1u);
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
}

/* Player inside rect, correct direction (S = facing south) -> clears */
void test_update_correct_direction_clears(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, DIR_B);   /* inside, facing south */
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
}

/* Wrong direction -> ignored */
void test_update_wrong_direction_ignored(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, DIR_T);   /* inside, facing north -- wrong */
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
}

/* Outside rect -> ignored */
void test_update_outside_rect_ignored(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(100, 100, 32, 32, 0u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, DIR_B);   /* outside rect */
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
}

/* Must clear in order: skipping cp0 for cp1 -> cp0 still pending */
void test_sequential_order_enforced(void) {
    CheckpointDef defs[2];
    defs[0] = make_cp(0,   0, 32, 32, 0u, CHECKPOINT_DIR_S);
    defs[1] = make_cp(100, 0, 32, 32, 1u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 2u);
    /* Try to clear cp1 first -- should be ignored */
    checkpoint_update(110, 5, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
    /* Now clear cp0 */
    checkpoint_update(5, 5, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared()); /* cp1 still pending */
    /* Now clear cp1 */
    checkpoint_update(110, 5, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
}

/* checkpoint_reset() resets cp_next to 0 */
void test_reset_restores_initial_state(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
    checkpoint_reset();
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
}

/* Direction N: facing north (DIR_T, DIR_RT, DIR_LT) required */
void test_direction_north_requires_north_facing(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_N);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, DIR_B);   /* facing south, wrong for N */
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
    checkpoint_update(5, 5, DIR_T);   /* facing north, correct for N */
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
}

/* Direction E: facing east (DIR_R, DIR_RT, DIR_RB) required */
void test_direction_east_requires_east_facing(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_E);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, DIR_L);   /* facing west, wrong */
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
    checkpoint_update(5, 5, DIR_R);   /* facing east, correct */
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
}

/* Direction W: facing west (DIR_L, DIR_LT, DIR_LB) required */
void test_direction_west_requires_west_facing(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_W);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, DIR_R);   /* facing east, wrong */
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
    checkpoint_update(5, 5, DIR_L);   /* facing west, correct */
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
}

void test_cp_next_exported_as_global(void) {
    extern uint8_t cp_next;
    checkpoint_init(NULL, 0u);
    TEST_ASSERT_EQUAL_UINT8(0u, cp_next);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_zero_checkpoints_all_cleared);
    RUN_TEST(test_one_checkpoint_not_cleared_at_init);
    RUN_TEST(test_update_correct_direction_clears);
    RUN_TEST(test_update_wrong_direction_ignored);
    RUN_TEST(test_update_outside_rect_ignored);
    RUN_TEST(test_sequential_order_enforced);
    RUN_TEST(test_reset_restores_initial_state);
    RUN_TEST(test_direction_north_requires_north_facing);
    RUN_TEST(test_direction_east_requires_east_facing);
    RUN_TEST(test_direction_west_requires_west_facing);
    RUN_TEST(test_cp_next_exported_as_global);
    return UNITY_END();
}
