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

/* Contract: music_tick() must NOT modify frame_ready.
 *
 * In the main loop, after music_tick() returns, main.c checks:
 *   if (frame_ready) continue;   // VBL fired during __critical — skip frame
 *
 * If music_tick() were to clear frame_ready, a genuine VBL miss would go
 * undetected and the double-tick race would resume silently.
 *
 * Host-side mocks cannot simulate a mid-__critical VBL interrupt. The actual
 * race condition is verified by Emulicious smoketest (run game past ~33s). */
void test_music_tick_does_not_clear_frame_ready(void) {
    frame_ready = 1;
    music_tick();
    TEST_ASSERT_EQUAL_UINT8(1u, frame_ready);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_vbl_display_off_consumes_frame_ready);
    RUN_TEST(test_music_tick_restores_bank);
    RUN_TEST(test_music_tick_does_not_clear_frame_ready);
    return UNITY_END();
}
