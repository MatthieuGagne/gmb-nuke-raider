#include "unity.h"
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

/* Player inside rect, correct direction (S = vy > 0) -> clears */
void test_update_correct_direction_clears(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, 0, 1);   /* inside, vy=1 (south) */
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
}

/* Wrong direction -> ignored */
void test_update_wrong_direction_ignored(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, 0, -1);  /* inside, vy=-1 (north) -- wrong */
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
}

/* Outside rect -> ignored */
void test_update_outside_rect_ignored(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(100, 100, 32, 32, 0u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, 0, 1);   /* outside rect */
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
}

/* Must clear in order: skipping cp0 for cp1 -> cp0 still pending */
void test_sequential_order_enforced(void) {
    CheckpointDef defs[2];
    defs[0] = make_cp(0,   0, 32, 32, 0u, CHECKPOINT_DIR_S);
    defs[1] = make_cp(100, 0, 32, 32, 1u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 2u);
    /* Try to clear cp1 first -- should be ignored */
    checkpoint_update(110, 5, 0, 1);
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
    /* Now clear cp0 */
    checkpoint_update(5, 5, 0, 1);
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared()); /* cp1 still pending */
    /* Now clear cp1 */
    checkpoint_update(110, 5, 0, 1);
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
}

/* checkpoint_reset() resets cp_next to 0 */
void test_reset_restores_initial_state(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_S);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, 0, 1);
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
    checkpoint_reset();
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
}

/* Direction N: vy < 0 required */
void test_direction_north_requires_negative_vy(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_N);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, 0, 1);   /* vy=1, wrong for N */
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
    checkpoint_update(5, 5, 0, -1);  /* vy=-1, correct for N */
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
}

/* Direction E: vx > 0 required */
void test_direction_east_requires_positive_vx(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_E);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, -1, 0);  /* wrong */
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
    checkpoint_update(5, 5, 1, 0);   /* correct */
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
}

/* Direction W: vx < 0 required */
void test_direction_west_requires_negative_vx(void) {
    CheckpointDef defs[1];
    defs[0] = make_cp(0, 0, 32, 32, 0u, CHECKPOINT_DIR_W);
    checkpoint_init(defs, 1u);
    checkpoint_update(5, 5, 1, 0);   /* wrong */
    TEST_ASSERT_EQUAL_UINT8(0u, checkpoint_all_cleared());
    checkpoint_update(5, 5, -1, 0);  /* correct */
    TEST_ASSERT_EQUAL_UINT8(1u, checkpoint_all_cleared());
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
    RUN_TEST(test_direction_north_requires_negative_vy);
    RUN_TEST(test_direction_east_requires_positive_vx);
    RUN_TEST(test_direction_west_requires_negative_vx);
    return UNITY_END();
}
