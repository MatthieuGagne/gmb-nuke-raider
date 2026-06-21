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

/* ---- patrol_fsm_next: hysteresis (R2 / AC1) ----
 * Deltas are derived from the config radii so retuning PATROL_DETECT_RADIUS /
 * PATROL_LEAVE_RADIUS never silently breaks these tests:
 *   FSM_IN  : Manhattan 2*FSM_IN  <  DETECT          (inside detect)
 *   FSM_MID : DETECT <= 2*FSM_MID <  LEAVE           (hysteresis band)
 *   FSM_OUT : Manhattan 2*FSM_OUT >= LEAVE           (outside leave)   */
#define FSM_IN  ((int16_t)(PATROL_DETECT_RADIUS / 2u - 1u))
#define FSM_MID ((int16_t)((PATROL_DETECT_RADIUS + PATROL_LEAVE_RADIUS) / 4u))
#define FSM_OUT ((int16_t)(PATROL_LEAVE_RADIUS / 2u + 4u))

void test_fsm_enters_chase_when_inside_detect(void) {
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_CHASE,
        patrol_fsm_next(PATROL_MODE_PATROL, FSM_IN, FSM_IN));
}

void test_fsm_stays_patrol_outside_detect(void) {
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_PATROL,
        patrol_fsm_next(PATROL_MODE_PATROL, FSM_OUT, FSM_OUT));
}

void test_fsm_returns_patrol_when_beyond_leave(void) {
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_PATROL,
        patrol_fsm_next(PATROL_MODE_CHASE, FSM_OUT, FSM_OUT));
}

void test_fsm_no_flicker_in_hysteresis_band(void) {
    /* In the band: PATROL stays PATROL; CHASE stays CHASE — no flicker. */
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_PATROL,
        patrol_fsm_next(PATROL_MODE_PATROL, FSM_MID, FSM_MID));
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_CHASE,
        patrol_fsm_next(PATROL_MODE_CHASE, FSM_MID, FSM_MID));
}

void test_fsm_handles_negative_deltas(void) {
    TEST_ASSERT_EQUAL_UINT8(PATROL_MODE_CHASE,
        patrol_fsm_next(PATROL_MODE_PATROL, (int16_t)-FSM_IN, (int16_t)-FSM_IN));
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
    /* Patrol at world (88,16), on-screen. Player 24px to the right: outside
     * the 16x16 ram overlap (so ram damage cannot confound the assertion) but
     * well within PATROL_FIRE_RADIUS; the bullet does not reach the player on
     * the firing frame, so a live projectile proves the patrol fired. */
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {2u};
    patrol_spawn_for_test(88, 16, wtx, wty, 1u);
    patrol_set_mode_for_test(0u, PATROL_MODE_CHASE);
    /* drive the fire timer to 0 so the first on-screen frame fires */
    patrol_set_fire_timer_for_test(0u, 0u);
    patrol_update(112, 16);  /* Manhattan ~19 after move < PATROL_FIRE_RADIUS */
    TEST_ASSERT_EQUAL_UINT8(1u, projectile_count_active());
}

/* ---- ram contact: car-vs-car overlap damages the player ---- */

void test_ram_contact_damages_player(void) {
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    damage_init();                       /* player HP = PLAYER_MAX_HP */
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_update(40, 32);   /* player 8px right → 16x16 boxes overlap → ram */
    TEST_ASSERT_TRUE(damage_get_hp() < PLAYER_MAX_HP);
}

void test_destroyed_patrol_deals_no_contact_damage(void) {
    /* A destroyed patrol (active=0) is skipped by patrol_update's pool guard,
     * so it must not ram the player even when their boxes overlap (#412). */
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_hp_for_test(0u, 1u);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    patrol_update(0, 0);                 /* lethal bullet, player far → no ram during kill */
    TEST_ASSERT_EQUAL_UINT8(0u, patrol_is_active(0u));
    damage_init();                       /* reset player HP after the kill frame */
    patrol_update(40, 32);               /* player overlaps the wreck's last position */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)PLAYER_MAX_HP, damage_get_hp());
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

/* ---- patrol enemy-side ram damage + hit-flash (#417) ---- */

void test_patrol_ram_reduces_hp(void) {
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    damage_init();
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_hp_for_test(0u, PATROL_HP);
    patrol_update(40, 32);   /* player 8px right -> 16x16 overlap -> ram */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PATROL_HP - ENEMY_RAM_DAMAGE), patrol_get_hp(0u));
}

void test_patrol_ram_debounced_by_cooldown(void) {
    /* Two consecutive overlapping updates deal only one enemy hit (cooldown). */
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    damage_init();
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_hp_for_test(0u, PATROL_HP);
    patrol_update(40, 32);   /* hp-1, cd = ENEMY_RAM_COOLDOWN */
    patrol_update(40, 32);   /* cd still > 0 after top-of-frame decrement -> no damage */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PATROL_HP - ENEMY_RAM_DAMAGE), patrol_get_hp(0u));
}

void test_patrol_ram_cooldown_expiry_allows_second_hit(void) {
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    damage_init();
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_hp_for_test(0u, PATROL_HP);
    patrol_update(40, 32);                  /* hp-1, cd set */
    patrol_set_ram_cd_for_test(0u, 1u);     /* next frame's top decrement -> 0 -> ram applies */
    patrol_update(40, 32);                  /* hp-1 again */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PATROL_HP - 2u * ENEMY_RAM_DAMAGE), patrol_get_hp(0u));
}

void test_patrol_ram_nonlethal_sets_hit_flash(void) {
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    damage_init();
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_hp_for_test(0u, PATROL_HP);
    patrol_update(40, 32);
    TEST_ASSERT_EQUAL_UINT8(RACER_HIT_FLASH_FRAMES, patrol_get_hit_flash(0u));
}

void test_patrol_ram_to_kill_destroys(void) {
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    damage_init();
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_hp_for_test(0u, ENEMY_RAM_DAMAGE);
    patrol_update(40, 32);
    TEST_ASSERT_EQUAL_UINT8(0u, patrol_is_active(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, patrol_count_active());
}

void test_patrol_bullet_hit_sets_hit_flash(void) {
    /* New: bullet hits now blink too (fixes the pre-existing no-blink gap). */
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_mode_for_test(0u, PATROL_MODE_PATROL);
    patrol_set_hp_for_test(0u, PATROL_HP);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    patrol_update(0, 0);     /* player far -> bullet hit, no ram */
    TEST_ASSERT_EQUAL_UINT8(RACER_HIT_FLASH_FRAMES, patrol_get_hit_flash(0u));
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
    RUN_TEST(test_ram_contact_damages_player);
    RUN_TEST(test_destroyed_patrol_deals_no_contact_damage);
    RUN_TEST(test_bullet_hit_decrements_hp);
    RUN_TEST(test_fatal_hit_destroys_and_deactivates);
    RUN_TEST(test_patrol_ram_reduces_hp);
    RUN_TEST(test_patrol_ram_debounced_by_cooldown);
    RUN_TEST(test_patrol_ram_cooldown_expiry_allows_second_hit);
    RUN_TEST(test_patrol_ram_nonlethal_sets_hit_flash);
    RUN_TEST(test_patrol_ram_to_kill_destroys);
    RUN_TEST(test_patrol_bullet_hit_sets_hit_flash);
    return UNITY_END();
}
