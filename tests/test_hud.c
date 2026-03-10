/* tests/test_hud.c — HUD timer logic and dirty-flag behavior */
#include "unity.h"
#include <gb/gb.h>
#include "../src/config.h"
#include "../src/hud.h"

void setUp(void) { hud_init(); }
void tearDown(void) {}

/* --- After init: state is zeroed and dirty is clear --- */

void test_init_seconds_zero(void) {
    TEST_ASSERT_EQUAL_UINT16(0u, hud_get_seconds());
}

void test_init_dirty_clear(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, hud_is_dirty());
}

/* --- Frame tick: 59 updates do NOT advance the second --- */

void test_update_no_second_before_60_frames(void) {
    uint8_t i;
    for (i = 0u; i < 59u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT16(0u, hud_get_seconds());
}

void test_update_not_dirty_before_60_frames(void) {
    uint8_t i;
    for (i = 0u; i < 59u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT8(0u, hud_is_dirty());
}

/* --- 60th update advances the second and sets dirty --- */

void test_update_advances_second_at_60_frames(void) {
    uint8_t i;
    for (i = 0u; i < 60u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT16(1u, hud_get_seconds());
}

void test_update_dirty_after_60_frames(void) {
    uint8_t i;
    for (i = 0u; i < 60u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT8(1u, hud_is_dirty());
}

/* --- hud_render() clears the dirty flag --- */

void test_render_clears_dirty(void) {
    uint8_t i;
    for (i = 0u; i < 60u; i++) hud_update();
    hud_render();
    TEST_ASSERT_EQUAL_UINT8(0u, hud_is_dirty());
}

/* --- Frame tick wraps: second frame after render advances normally --- */

void test_second_frame_after_render(void) {
    uint8_t i;
    /* First second */
    for (i = 0u; i < 60u; i++) hud_update();
    hud_render();
    /* 59 more updates should NOT advance second again */
    for (i = 0u; i < 59u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT16(1u, hud_get_seconds());
    TEST_ASSERT_EQUAL_UINT8(0u, hud_is_dirty());
    /* 60th update DOES advance second */
    hud_update();
    TEST_ASSERT_EQUAL_UINT16(2u, hud_get_seconds());
    TEST_ASSERT_EQUAL_UINT8(1u, hud_is_dirty());
}

/* --- Three seconds: 180 updates --- */

void test_three_seconds(void) {
    uint8_t i;
    for (i = 0u; i < 180u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT16(3u, hud_get_seconds());
}

/* --- One minute: 3600 updates --- */

void test_one_minute(void) {
    uint16_t i;
    for (i = 0u; i < 3600u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT16(60u, hud_get_seconds());
}

/* --- hud_set_hp sets dirty flag --- */

void test_set_hp_sets_dirty(void) {
    /* After init, dirty is clear */
    TEST_ASSERT_EQUAL_UINT8(0u, hud_is_dirty());
    /* hud_set_hp must set dirty */
    hud_set_hp(50u);
    TEST_ASSERT_EQUAL_UINT8(1u, hud_is_dirty());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_seconds_zero);
    RUN_TEST(test_init_dirty_clear);
    RUN_TEST(test_update_no_second_before_60_frames);
    RUN_TEST(test_update_not_dirty_before_60_frames);
    RUN_TEST(test_update_advances_second_at_60_frames);
    RUN_TEST(test_update_dirty_after_60_frames);
    RUN_TEST(test_render_clears_dirty);
    RUN_TEST(test_second_frame_after_render);
    RUN_TEST(test_three_seconds);
    RUN_TEST(test_one_minute);
    RUN_TEST(test_set_hp_sets_dirty);
    return UNITY_END();
}
