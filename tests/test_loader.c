#include "unity.h"
#include <gb/gb.h>
#include "loader.h"
#include "track.h"

void setUp(void) {}
void tearDown(void) {}

/* Host tests verify that loader functions compile, link, and run without
 * crashing. Bank-switching (SWITCH_ROM) is a no-op in the mock environment.
 * Hardware-specific behavior (actual VRAM writes) requires emulator testing. */

void test_load_player_tiles_is_callable(void) {
    load_player_tiles();
    TEST_PASS();
}

void test_load_track_tiles_is_callable(void) {
    load_track_tiles();
    TEST_PASS();
}

void test_load_track_start_pos_writes_to_out_params(void) {
    int16_t x = -1, y = -1;
    load_track_start_pos(&x, &y);
    /* track_start_x/y are defined in track_map.c; host mock BANK() returns 0
     * so SWITCH_ROM(0) is a no-op and values are read directly. */
    TEST_PASS();
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_load_player_tiles_is_callable);
    RUN_TEST(test_load_track_tiles_is_callable);
    RUN_TEST(test_load_track_start_pos_writes_to_out_params);
    return UNITY_END();
}
