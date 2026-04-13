#include "unity.h"
#include "music.h"
#include "music_data.h"

void setUp(void)    { frame_ready = 0; _current_bank_mock = 0; }
void tearDown(void) {}

/* vbl_display_off() should consume the frame_ready flag (set it to 0).
 * We pre-set frame_ready = 1 so the spin loop exits immediately. */
void test_vbl_display_off_consumes_frame_ready(void) {
    frame_ready = 1;
    vbl_display_off();
    TEST_ASSERT_EQUAL_UINT8(0u, frame_ready);
}

/* Verifies music_tick() restores CURRENT_BANK after the bank switch.
 * Note: host-side mocks cannot simulate VBlank interrupts, so this is a
 * contract/regression test — it documents the invariant and catches any
 * future removal of the save/restore logic. The hardware race (missing
 * __critical) is verified by the Emulicious smoketest at ~24s. */
void test_music_tick_restores_bank(void) {
    _current_bank_mock = 5;
    music_tick();
    TEST_ASSERT_EQUAL_UINT8(5, _current_bank_mock);
}

/* order_cnt is a byte-offset count (2 bytes per pattern × 68 patterns = 136).
 * A wrong value (e.g. 68) causes the song to loop at half length. */
void test_music_data_order_cnt_is_136(void) {
    TEST_ASSERT_EQUAL_UINT8(136u, *music_data_song.order_cnt);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_vbl_display_off_consumes_frame_ready);
    RUN_TEST(test_music_tick_restores_bank);
    RUN_TEST(test_music_data_order_cnt_is_136);
    return UNITY_END();
}
