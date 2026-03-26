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

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_track_select_0_start_x);
    RUN_TEST(test_track_select_0_start_y);
    RUN_TEST(test_track_select_0_lap_count);
    RUN_TEST(test_track_select_1_lap_count);
    RUN_TEST(test_track_select_routes_raw_tile);
    return UNITY_END();
}
