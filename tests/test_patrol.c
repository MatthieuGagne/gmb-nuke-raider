#include "unity.h"
#include "patrol.h"
#include "projectile.h"
#include "player.h"   /* player_dir_t, DIR_* */
#include "damage.h"   /* damage_init, damage_get_hp */
#include "config.h"

/* cam_x/cam_y defined in camera.c — declared here as int16_t (host pattern,
 * matches racer.c); do NOT include camera.h (volatile uint16_t) to avoid a
 * conflicting-qualifier error. */
extern int16_t cam_x;
extern int16_t cam_y;

void setUp(void) {
    cam_x = 0;
    cam_y = 0;
    patrol_init_empty();
    projectile_init(0u);
}
void tearDown(void) {}

/* ---- patrol_fsm_next: hysteresis (R2 / AC1) ---- */

void test_fsm_enters_chase_when_inside_detect(void) {
    /* Manhattan |dx|+|dy| = 10 < 24 → enter CHASE from PATROL */
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_CHASE,
        patrol_fsm_next(PATROL_MODE_PATROL, 6, 4));
}

void test_fsm_stays_patrol_outside_detect(void) {
    /* Manhattan = 40 >= 24 → stay PATROL */
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_PATROL,
        patrol_fsm_next(PATROL_MODE_PATROL, 20, 20));
}

void test_fsm_returns_patrol_when_beyond_leave(void) {
    /* Manhattan = 40 >= 32 → CHASE returns to PATROL */
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_PATROL,
        patrol_fsm_next(PATROL_MODE_CHASE, 20, 20));
}

void test_fsm_no_flicker_in_hysteresis_band(void) {
    /* Manhattan = 28: >= detect(24) but < leave(32).
     * PATROL stays PATROL; CHASE stays CHASE — no flicker. */
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_PATROL,
        patrol_fsm_next(PATROL_MODE_PATROL, 14, 14));
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_CHASE,
        patrol_fsm_next(PATROL_MODE_CHASE, 14, 14));
}

void test_fsm_handles_negative_deltas(void) {
    /* |dx|+|dy| = 10 < 24, negative components → CHASE */
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_CHASE,
        patrol_fsm_next(PATROL_MODE_PATROL, -6, -4));
}

/* ---- spawn / init (R8 / AC3 setup) ---- */

void test_pool_empty_after_init_empty(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, patrol_count_active());
}

void test_spawn_for_test_activates_one(void) {
    static uint8_t wtx[2] = {11u, 11u};
    static uint8_t wty[2] = {30u, 40u};
    patrol_spawn_for_test(88, 240, wtx, wty, 2u);
    TEST_ASSERT_EQUAL_UINT8(1u, patrol_count_active());
    TEST_ASSERT_EQUAL_UINT8(1u, patrol_is_active(0u));
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_PATROL, patrol_get_state(0u));
    TEST_ASSERT_EQUAL_UINT8(PATROL_HP, patrol_get_hp(0u));
    TEST_ASSERT_EQUAL_INT16(88, patrol_get_px(0u));
    TEST_ASSERT_EQUAL_INT16(240, patrol_get_py(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, patrol_get_wp_idx(0u));
}

/* ---- waypoint advance + wrap (R3) ---- */

void test_wp_advances_when_reached_then_wraps(void) {
    /* 2 waypoints. Patrol parked on top of waypoint 0 → reaches it,
     * advances to 1; next reach wraps back to 0. */
    static uint8_t wtx[2] = {11u, 11u};
    static uint8_t wty[2] = {30u, 31u};
    patrol_spawn_for_test((int16_t)(11 * 8), (int16_t)(30 * 8), wtx, wty, 2u);
    patrol_set_mode_for_test(0u, PATROL_MODE_PATROL);

    patrol_update(0, 0);   /* player far away → stays PATROL, on top of wp0 → advance */
    TEST_ASSERT_EQUAL_UINT8(1u, patrol_get_wp_idx(0u));

    /* Teleport onto waypoint 1, run again → wrap to 0 */
    patrol_set_pos_for_test(0u, (int16_t)(11 * 8), (int16_t)(31 * 8));
    patrol_update(0, 0);
    TEST_ASSERT_EQUAL_UINT8(0u, patrol_get_wp_idx(0u));
}

/* ---- off-screen roaming but no fire (R5 / AC5) ---- */

void test_no_fire_when_off_screen(void) {
    /* Patrol far below the camera (off-screen). Player adjacent in world
     * space so CHASE+fire-radius would otherwise trigger. cam_y=0. */
    static uint8_t wtx[2] = {11u, 11u};
    static uint8_t wty[2] = {200u, 201u};
    patrol_spawn_for_test((int16_t)(11 * 8), (int16_t)(200 * 8), wtx, wty, 2u);
    patrol_set_mode_for_test(0u, PATROL_MODE_CHASE);
    /* player at same world pos → within fire radius, but patrol off-screen */
    patrol_update((int16_t)(11 * 8), (int16_t)(200 * 8));
    TEST_ASSERT_EQUAL_UINT8(0u, projectile_count_active());
}

/* ---- on-screen + chase + in fire radius → fires (R4 / AC2) ---- */

void test_fires_when_on_screen_chasing_in_range(void) {
    /* Patrol at world (88,16): scr_y = 16 - cam_y(0) + 16 = 32 ∈ [0,160),
     * scr_x = 88 - cam_x(0) + 8 ... on-screen. Player adjacent (point blank).
     * A chasing patrol at point-blank fires AND its bullet hits the player the
     * same frame (consumed by the end-of-update enemy-bullet-vs-player check),
     * dealing damage. Asserting "player took damage" is the robust proxy for
     * "the patrol fired" — counting a surviving projectile is fragile because a
     * close-range enemy shot is consumed on the firing frame. */
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {2u};
    damage_init();                       /* player HP = PLAYER_MAX_HP */
    patrol_spawn_for_test(88, 16, wtx, wty, 1u);
    patrol_set_mode_for_test(0u, PATROL_MODE_CHASE);
    /* drive the fire timer to 0 so the first on-screen frame fires */
    patrol_set_fire_timer_for_test(0u, 0u);
    patrol_update(88, 16);   /* player on top → Manhattan 0 < PATROL_FIRE_RADIUS */
    TEST_ASSERT_TRUE(damage_get_hp() < PLAYER_MAX_HP);  /* fired and hit player */
}

/* ---- hit → hp-- → destroy + free (R6 / AC3) ---- */

void test_bullet_hit_decrements_hp(void) {
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_mode_for_test(0u, PATROL_MODE_PATROL);
    patrol_set_hp_for_test(0u, PATROL_HP);
    /* Player bullet at patrol screen-center: scr_x=32+8=... use racer's proven
     * geometry: world (32,32) → scr (48,56) with cam_y=0. */
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    patrol_update(0, 0);
    TEST_ASSERT_EQUAL_UINT8(PATROL_HP - 1u, patrol_get_hp(0u));
}

void test_fatal_hit_destroys_and_deactivates(void) {
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_mode_for_test(0u, PATROL_MODE_PATROL);
    patrol_set_hp_for_test(0u, 1u);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    patrol_update(0, 0);
    TEST_ASSERT_EQUAL_UINT8(0u, patrol_is_active(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, patrol_count_active());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_fsm_enters_chase_when_inside_detect);
    RUN_TEST(test_fsm_stays_patrol_outside_detect);
    RUN_TEST(test_fsm_returns_patrol_when_beyond_leave);
    RUN_TEST(test_fsm_no_flicker_in_hysteresis_band);
    RUN_TEST(test_fsm_handles_negative_deltas);
    RUN_TEST(test_pool_empty_after_init_empty);
    RUN_TEST(test_spawn_for_test_activates_one);
    RUN_TEST(test_wp_advances_when_reached_then_wraps);
    RUN_TEST(test_no_fire_when_off_screen);
    RUN_TEST(test_fires_when_on_screen_chasing_in_range);
    RUN_TEST(test_bullet_hit_decrements_hp);
    RUN_TEST(test_fatal_hit_destroys_and_deactivates);
    return UNITY_END();
}
