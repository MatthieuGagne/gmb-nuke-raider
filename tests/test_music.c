#include "unity.h"
#include "music.h"

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

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_vbl_display_off_consumes_frame_ready);
    RUN_TEST(test_music_tick_restores_bank);
    return UNITY_END();
}
