#include "unity.h"
#include <gb/gb.h>
#include "explosion.h"
#include "../src/config.h"

/* tile_base values used in tests — arbitrary, not linked to any real VRAM slot */
#define T_BASE 20u
#define C_BASE 23u

void setUp(void) {
    mock_move_sprite_reset();
}
void tearDown(void) {}

/* ── init ─────────────────────────────────────────────────────────────── */

void test_explosion_init_empty(void) {
    explosion_init(T_BASE, C_BASE);
    TEST_ASSERT_EQUAL_UINT8(0, explosion_active_count());
    TEST_ASSERT_TRUE(explosion_is_done());   /* no car blast => done */
}

/* ── spawn + render ────────────────────────────────────────────────────── */

void test_turret_spawn_starts_frame0(void) {
    explosion_init(T_BASE, C_BASE);
    explosion_spawn(5u, T_BASE, 0u, 0u);
    TEST_ASSERT_EQUAL_UINT8(1, explosion_active_count());
    explosion_render();
    TEST_ASSERT_EQUAL_UINT8(T_BASE + 0u, mock_sprite_tile[5]);
}

/* ── frame advance ─────────────────────────────────────────────────────── */

void test_frame_advances_every_40_ticks(void) {
    explosion_init(T_BASE, C_BASE);
    explosion_spawn(5u, T_BASE, 0u, 0u);
    uint8_t i;
    for (i = 0u; i < 40u; i++) explosion_update();
    explosion_render();
    TEST_ASSERT_EQUAL_UINT8(T_BASE + 1u, mock_sprite_tile[5]);  /* frame 1 */
    for (i = 0u; i < 40u; i++) explosion_update();
    explosion_render();
    TEST_ASSERT_EQUAL_UINT8(T_BASE + 2u, mock_sprite_tile[5]);  /* frame 2 */
}

/* ── completion + OAM free ─────────────────────────────────────────────── */

void test_completes_and_frees_oam_after_120_ticks(void) {
    uint8_t i;
    explosion_init(T_BASE, C_BASE);
    explosion_spawn(5u, T_BASE, 0u, 0u);
    for (i = 0u; i < 120u; i++) explosion_update();
    TEST_ASSERT_EQUAL_UINT8(0, explosion_active_count());
    /* clear_sprite(slot) calls move_sprite(slot, 0, 0) — verify it was called */
    TEST_ASSERT_GREATER_THAN(0, mock_move_sprite_call_count);
}

/* ── concurrent entries ────────────────────────────────────────────────── */

void test_two_explosions_independent_frames(void) {
    uint8_t i;
    explosion_init(T_BASE, C_BASE);
    explosion_spawn(5u, T_BASE, 0u, 0u);
    for (i = 0u; i < 40u; i++) explosion_update();  /* #1 -> frame 1 */
    explosion_spawn(6u, T_BASE, 0u, 0u);             /* #2 -> frame 0 */
    explosion_render();
    TEST_ASSERT_EQUAL_UINT8(T_BASE + 1u, mock_sprite_tile[5]);
    TEST_ASSERT_EQUAL_UINT8(T_BASE + 0u, mock_sprite_tile[6]);
}

/* ── car-blast done gate ───────────────────────────────────────────────── */

void test_car_blast_gates_done(void) {
    uint8_t i;
    explosion_init(T_BASE, C_BASE);
    explosion_spawn(0u, C_BASE, 0u,                      1u);  /* TL, is_car */
    explosion_spawn(2u, C_BASE, S_FLIPX,                 1u);  /* TR */
    explosion_spawn(1u, C_BASE, S_FLIPY,                 1u);  /* BL */
    explosion_spawn(3u, C_BASE, (uint8_t)(S_FLIPX|S_FLIPY), 1u);  /* BR */
    TEST_ASSERT_FALSE(explosion_is_done());  /* car blast active */
    for (i = 0u; i < 120u; i++) explosion_update();
    TEST_ASSERT_TRUE(explosion_is_done());   /* car blast finished */
}

/* ── pool capacity ─────────────────────────────────────────────────────── */

void test_pool_full_drops_extra(void) {
    uint8_t i;
    explosion_init(T_BASE, C_BASE);
    for (i = 0u; i < MAX_EXPLOSIONS; i++) explosion_spawn(i, T_BASE, 0u, 0u);
    explosion_spawn(30u, T_BASE, 0u, 0u);  /* 13th — dropped */
    TEST_ASSERT_EQUAL_UINT8(MAX_EXPLOSIONS, explosion_active_count());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_explosion_init_empty);
    RUN_TEST(test_turret_spawn_starts_frame0);
    RUN_TEST(test_frame_advances_every_40_ticks);
    RUN_TEST(test_completes_and_frees_oam_after_120_ticks);
    RUN_TEST(test_two_explosions_independent_frames);
    RUN_TEST(test_car_blast_gates_done);
    RUN_TEST(test_pool_full_drops_extra);
    return UNITY_END();
}
