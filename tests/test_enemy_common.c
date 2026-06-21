/* tests/test_enemy_common.c */
#include "unity.h"
#include "enemy_common.h"
#include "player.h"   /* player_dir_t: DIR_T, DIR_R, DIR_NNE, ... */
#include "config.h"

void setUp(void) {}
void tearDown(void) {}

/* ---- enemy_aim_dir: ported verbatim from the old turret aim cases ---- */

void test_aim_right(void) {
    /* Source at tile (0,0) = pixel (0,0); player at (64,0) -> DIR_R */
    TEST_ASSERT_EQUAL_INT(DIR_R, enemy_aim_dir(0u, 0u, 64, 0));
}
void test_aim_down(void) {
    TEST_ASSERT_EQUAL_INT(DIR_B, enemy_aim_dir(0u, 0u, 0, 64));
}
void test_aim_down_right(void) {
    /* ax==ay==64, toward_x=0, SE quadrant -> DIR_SSE */
    TEST_ASSERT_EQUAL_INT(DIR_SSE, enemy_aim_dir(0u, 0u, 64, 64));
}
void test_aim_up_left(void) {
    /* ax==ay==80, toward_x=0, NW quadrant -> DIR_NNW */
    TEST_ASSERT_EQUAL_INT(DIR_NNW, enemy_aim_dir(10u, 10u, 0, 0));
}
void test_aim_nne(void) {
    TEST_ASSERT_EQUAL_INT(DIR_NNE, enemy_aim_dir(0u, 0u, 10, -15));
}
void test_aim_ene(void) {
    TEST_ASSERT_EQUAL_INT(DIR_ENE, enemy_aim_dir(0u, 0u, 15, -10));
}
void test_aim_ese(void) {
    TEST_ASSERT_EQUAL_INT(DIR_ESE, enemy_aim_dir(0u, 0u, 15, 10));
}
void test_aim_sse(void) {
    TEST_ASSERT_EQUAL_INT(DIR_SSE, enemy_aim_dir(0u, 0u, 10, 15));
}
void test_aim_ssw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_SSW, enemy_aim_dir(0u, 0u, -10, 15));
}
void test_aim_wsw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_WSW, enemy_aim_dir(0u, 0u, -15, 10));
}
void test_aim_wnw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_WNW, enemy_aim_dir(0u, 0u, -15, -10));
}
void test_aim_nnw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_NNW, enemy_aim_dir(0u, 0u, -10, -15));
}

/* ---- enemy_dir_from_delta: one case per 8-way DIR_* ---- */

void test_dir_from_delta_up(void) {
    /* ay>ax, dy<0 -> DIR_T */
    TEST_ASSERT_EQUAL_UINT8(DIR_T, enemy_dir_from_delta(0, -5));
}
void test_dir_from_delta_down(void) {
    /* ay>ax, dy>0 -> DIR_B */
    TEST_ASSERT_EQUAL_UINT8(DIR_B, enemy_dir_from_delta(0, 5));
}
void test_dir_from_delta_left(void) {
    /* ax>ay, dx<0 -> DIR_L */
    TEST_ASSERT_EQUAL_UINT8(DIR_L, enemy_dir_from_delta(-5, 0));
}
void test_dir_from_delta_right(void) {
    /* ax>ay, dx>0 -> DIR_R */
    TEST_ASSERT_EQUAL_UINT8(DIR_R, enemy_dir_from_delta(5, 0));
}
void test_dir_from_delta_up_left(void) {
    /* ax==ay, dy<0 && dx<0 -> DIR_LT */
    TEST_ASSERT_EQUAL_UINT8(DIR_LT, enemy_dir_from_delta(-5, -5));
}
void test_dir_from_delta_up_right(void) {
    /* ax==ay, dy<0 && dx>0 -> DIR_RT */
    TEST_ASSERT_EQUAL_UINT8(DIR_RT, enemy_dir_from_delta(5, -5));
}
void test_dir_from_delta_down_left(void) {
    /* ax==ay, dy>0 && dx<0 -> DIR_LB */
    TEST_ASSERT_EQUAL_UINT8(DIR_LB, enemy_dir_from_delta(-5, 5));
}
void test_dir_from_delta_down_right(void) {
    /* ax==ay, dy>0 && dx>0 (else branch) -> DIR_RB */
    TEST_ASSERT_EQUAL_UINT8(DIR_RB, enemy_dir_from_delta(5, 5));
}

/* ---- enemy_wp_reached: boundary tests around the threshold ---- */

void test_wp_reached_below_threshold(void) {
    /* |3|+|3|=6 < 12 -> reached */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_wp_reached(3, 3, 12u));
}
void test_wp_reached_at_threshold_not_reached(void) {
    /* |6|+|6|=12, NOT < 12 -> not reached */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_wp_reached(6, 6, 12u));
}
void test_wp_reached_just_below_threshold(void) {
    /* |6|+|5|=11 < 12 -> reached */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_wp_reached(6, 5, 12u));
}
void test_wp_reached_just_above_threshold(void) {
    /* |7|+|6|=13, NOT < 12 -> not reached */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_wp_reached(7, 6, 12u));
}
void test_wp_reached_negative_deltas(void) {
    /* abs handles negatives: |-3|+|-3|=6 < 12 -> reached */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_wp_reached(-3, -3, 12u));
}
void test_wp_reached_zero_distance(void) {
    /* 0 < 12 -> reached */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_wp_reached(0, 0, 12u));
}

/* ---- enemy_wp_advance: advance + wrap behavior ---- */

void test_wp_advance_not_reached_keeps_index(void) {
    /* reached=0 -> index unchanged */
    TEST_ASSERT_EQUAL_UINT8(2u, enemy_wp_advance(2u, 4u, 0u));
}
void test_wp_advance_reached_increments(void) {
    /* reached=1, 0+1=1 < 4 -> 1 */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_wp_advance(0u, 4u, 1u));
}
void test_wp_advance_reached_wraps_at_last(void) {
    /* reached=1, 3+1=4 >= 4 -> wrap to 0 */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_wp_advance(3u, 4u, 1u));
}
void test_wp_advance_single_waypoint_wraps_to_self(void) {
    /* count=1: reached=1, 0+1=1 >= 1 -> wrap to 0 */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_wp_advance(0u, 1u, 1u));
}
void test_wp_advance_mid_route(void) {
    /* reached=1, 1+1=2 < 4 -> 2 */
    TEST_ASSERT_EQUAL_UINT8(2u, enemy_wp_advance(1u, 4u, 1u));
}

/* ---- enemy_ram_overlap: ram box with ENEMY_RAM_REACH margin, any side (#417) ----
 * Enemy AABB is [32,48) x [32,48) throughout. */

void test_ram_overlap_when_interpenetrating(void) {
    /* Player box overlapping the enemy interior -> ram. */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_ram_overlap(40, 40, 32, 32));
}

void test_ram_overlap_flush_above(void) {
    /* Player flush above: player [16,32) touches enemy top edge (gap 0). The
     * strict AABB would miss; the ENEMY_RAM_REACH margin makes it ram. */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_ram_overlap(32, 16, 32, 32));
}
void test_ram_overlap_flush_below(void) {
    /* Player flush below (the "from behind" case when the enemy heads up). */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_ram_overlap(32, 48, 32, 32));
}
void test_ram_overlap_flush_left(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_ram_overlap(16, 32, 32, 32));
}
void test_ram_overlap_flush_right(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_ram_overlap(48, 32, 32, 32));
}

void test_ram_overlap_misses_beyond_reach(void) {
    /* A clear gap of ENEMY_RAM_REACH px below the enemy -> no ram. */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_ram_overlap(32, (int16_t)(48 + ENEMY_RAM_REACH), 32, 32));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_aim_right);
    RUN_TEST(test_aim_down);
    RUN_TEST(test_aim_down_right);
    RUN_TEST(test_aim_up_left);
    RUN_TEST(test_aim_nne);
    RUN_TEST(test_aim_ene);
    RUN_TEST(test_aim_ese);
    RUN_TEST(test_aim_sse);
    RUN_TEST(test_aim_ssw);
    RUN_TEST(test_aim_wsw);
    RUN_TEST(test_aim_wnw);
    RUN_TEST(test_aim_nnw);
    RUN_TEST(test_dir_from_delta_up);
    RUN_TEST(test_dir_from_delta_down);
    RUN_TEST(test_dir_from_delta_left);
    RUN_TEST(test_dir_from_delta_right);
    RUN_TEST(test_dir_from_delta_up_left);
    RUN_TEST(test_dir_from_delta_up_right);
    RUN_TEST(test_dir_from_delta_down_left);
    RUN_TEST(test_dir_from_delta_down_right);
    RUN_TEST(test_wp_reached_below_threshold);
    RUN_TEST(test_wp_reached_at_threshold_not_reached);
    RUN_TEST(test_wp_reached_just_below_threshold);
    RUN_TEST(test_wp_reached_just_above_threshold);
    RUN_TEST(test_wp_reached_negative_deltas);
    RUN_TEST(test_wp_reached_zero_distance);
    RUN_TEST(test_wp_advance_not_reached_keeps_index);
    RUN_TEST(test_wp_advance_reached_increments);
    RUN_TEST(test_wp_advance_reached_wraps_at_last);
    RUN_TEST(test_wp_advance_single_waypoint_wraps_to_self);
    RUN_TEST(test_wp_advance_mid_route);
    RUN_TEST(test_ram_overlap_when_interpenetrating);
    RUN_TEST(test_ram_overlap_flush_above);
    RUN_TEST(test_ram_overlap_flush_below);
    RUN_TEST(test_ram_overlap_flush_left);
    RUN_TEST(test_ram_overlap_flush_right);
    RUN_TEST(test_ram_overlap_misses_beyond_reach);
    return UNITY_END();
}
