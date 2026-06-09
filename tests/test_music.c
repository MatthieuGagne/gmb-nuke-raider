#include "unity.h"
#include "music.h"
#include "music_data.h"
#include "config.h"
extern int hUGE_dosound_call_count;  /* tests/mocks/hUGEDriver_mock.c */

void setUp(void) {
    frame_ready = 0;
    _current_bank_mock = 0;
    hUGE_dosound_call_count = 0;
    music_resync();
}
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

/* music_service() with one owed VBlank runs exactly one driver tick. */
void test_music_service_one_owed_runs_one_tick(void) {
    music_resync();
    music_notify_vblank();                 /* owed = 1 */
    hUGE_dosound_call_count = 0;
    {
        uint8_t ran = music_service();
        TEST_ASSERT_EQUAL_UINT8(1u, ran);
    }
    TEST_ASSERT_EQUAL_INT(1, hUGE_dosound_call_count);
    TEST_ASSERT_EQUAL_UINT8(0u, music_ticks_owed_peek());
}

/* Three owed VBlanks (within the cap) run three driver ticks. */
void test_music_service_three_owed_runs_three_ticks(void) {
    music_resync();
    music_notify_vblank(); music_notify_vblank(); music_notify_vblank();
    hUGE_dosound_call_count = 0;
    {
        uint8_t ran = music_service();
        TEST_ASSERT_EQUAL_UINT8(3u, ran);
    }
    TEST_ASSERT_EQUAL_INT(3, hUGE_dosound_call_count);
    TEST_ASSERT_EQUAL_UINT8(0u, music_ticks_owed_peek());
}

/* Owed above MUSIC_MAX_CATCHUP clamps the drain but still fully zeroes the counter. */
void test_music_service_clamps_to_cap(void) {
    uint8_t k;
    music_resync();
    for (k = 0u; k < 10u; k++) music_notify_vblank();
    hUGE_dosound_call_count = 0;
    {
        uint8_t ran = music_service();
        TEST_ASSERT_EQUAL_UINT8((uint8_t)MUSIC_MAX_CATCHUP, ran);
    }
    TEST_ASSERT_EQUAL_INT((int)MUSIC_MAX_CATCHUP, hUGE_dosound_call_count);
    TEST_ASSERT_EQUAL_UINT8(0u, music_ticks_owed_peek());
}

/* The counter saturates at 255 and never wraps to 0. */
void test_music_notify_saturates_at_255(void) {
    uint16_t k;
    music_resync();
    for (k = 0u; k < 300u; k++) music_notify_vblank();
    TEST_ASSERT_EQUAL_UINT8(255u, music_ticks_owed_peek());
}

/* music_resync() zeroes a non-zero counter. */
void test_music_resync_zeroes_counter(void) {
    music_notify_vblank(); music_notify_vblank();
    music_resync();
    TEST_ASSERT_EQUAL_UINT8(0u, music_ticks_owed_peek());
}

/* vbl_display_off() ticks exactly once and accounts for the VBlank it consumed,
 * so a following music_service() will not re-tick it (no double-tick). */
void test_vbl_display_off_accounts_one_tick(void) {
    music_resync();
    music_notify_vblank(); music_notify_vblank();   /* owed = 2 (simulate ISR) */
    frame_ready = 1;
    hUGE_dosound_call_count = 0;
    vbl_display_off();
    TEST_ASSERT_EQUAL_INT(1, hUGE_dosound_call_count);
    TEST_ASSERT_EQUAL_UINT8(1u, music_ticks_owed_peek());
}
int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_vbl_display_off_consumes_frame_ready);
    RUN_TEST(test_music_tick_restores_bank);
    RUN_TEST(test_music_data_order_cnt_is_136);
    RUN_TEST(test_music_service_one_owed_runs_one_tick);
    RUN_TEST(test_music_service_three_owed_runs_three_ticks);
    RUN_TEST(test_music_service_clamps_to_cap);
    RUN_TEST(test_music_notify_saturates_at_255);
    RUN_TEST(test_music_resync_zeroes_counter);
    RUN_TEST(test_vbl_display_off_accounts_one_tick);
    return UNITY_END();
}
