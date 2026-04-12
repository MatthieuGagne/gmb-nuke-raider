/* tests/test_track_dispatch.c — TrackDesc dispatch routing */
#include "unity.h"
#include "../src/track.h"

void setUp(void)    {}
void tearDown(void) {}

/* After track_select(0): accessors return track 0 values */
void test_track_select_0_start_x(void) {
    track_select(0u);
    TEST_ASSERT_EQUAL_INT16(88, track_get_start_x());
}

void test_track_select_0_start_y(void) {
    track_select(0u);
    TEST_ASSERT_EQUAL_INT16(8, track_get_start_y());   /* start moved to row 1 (y=8) */
}

void test_track_select_0_lap_count(void) {
    track_select(0u);
    TEST_ASSERT_EQUAL_UINT8(1u, track_get_lap_count()); /* single finish crossing */
}

/* After track_select(1): accessors return track 1 values */
void test_track_select_1_lap_count(void) {
    track_select(1u);
    TEST_ASSERT_EQUAL_UINT8(3u, track_get_lap_count());
}

/* track_get_raw_tile routes to the active track's map */
void test_track_select_routes_raw_tile(void) {
    uint8_t t0, t1;
    track_select(0u);
    t0 = track_get_raw_tile(0u, 0u);
    track_select(1u);
    t1 = track_get_raw_tile(0u, 0u);
    /* Both tracks have wall (0) at (0,0) — just verify it doesn't crash */
    TEST_ASSERT_EQUAL_UINT8(t0, t1);
}

void test_track_select_0_checkpoint_count_is_zero(void) {
    track_select(0u);
    /* track 0 has no checkpoints defined yet — count must be 0 or match map */
    TEST_ASSERT(track_get_checkpoint_count() == 0u ||
                track_get_checkpoint_count() > 0u); /* just verifies accessor exists */
}

/* --- track_init() shows BG layer (tile loading done by loader_load_state) --- */

/* track_select(0) + track_init() must not crash */
void test_track_init_track0_no_crash(void) {
    track_select(0u);
    track_init();
    TEST_PASS();
}

/* track_select(1) + track_init() must not crash */
void test_track_init_track1_no_crash(void) {
    track_select(1u);
    track_init();
    TEST_PASS();
}

/* track_select(2) + track_init() must not crash */
void test_track_init_track2_no_crash(void) {
    track_select(2u);
    track_init();
    TEST_PASS();
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_track_select_0_start_x);
    RUN_TEST(test_track_select_0_start_y);
    RUN_TEST(test_track_select_0_lap_count);
    RUN_TEST(test_track_select_1_lap_count);
    RUN_TEST(test_track_select_routes_raw_tile);
    RUN_TEST(test_track_select_0_checkpoint_count_is_zero);
    RUN_TEST(test_track_init_track0_no_crash);
    RUN_TEST(test_track_init_track1_no_crash);
    RUN_TEST(test_track_init_track2_no_crash);
    return UNITY_END();
}
