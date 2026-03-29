/* tests/test_sfx.c */
#include "unity.h"
#include "sfx.h"
#include "hUGEDriver.h"
#include "gb/hardware.h"

/* Tracking globals from hUGEDriver_mock.c */
extern int hUGE_mute_channel_call_count;
extern enum hUGE_channel_t hUGE_mute_last_channel;
extern enum hUGE_mute_t    hUGE_mute_last_mute;

void setUp(void) {
    sfx_init();
    hUGE_mute_channel_call_count = 0;
    NR41_REG = 0; NR42_REG = 0; NR43_REG = 0; NR44_REG = 0;
}
void tearDown(void) {}

/* sfx_init() leaves all slots inactive */
void test_sfx_init_clears_pool(void) {
    /* sfx_init called in setUp — verify pool is empty via sfx_active_count() */
    TEST_ASSERT_EQUAL_UINT8(0u, sfx_active_count());
}

/* sfx_play(SFX_EXPLOSION) steals CH4 and triggers APU */
void test_sfx_play_explosion_mutes_ch4(void) {
    sfx_play(SFX_EXPLOSION);
    TEST_ASSERT_EQUAL_INT(1, hUGE_mute_channel_call_count);
    TEST_ASSERT_EQUAL_INT(HT_CH4, hUGE_mute_last_channel);
    TEST_ASSERT_EQUAL_INT(HT_CH_MUTE, hUGE_mute_last_mute);
}

/* sfx_play writes NR44 trigger bit */
void test_sfx_play_triggers_apu_ch4(void) {
    sfx_play(SFX_EXPLOSION);
    TEST_ASSERT_NOT_EQUAL(0u, NR44_REG & 0x80u);  /* trigger bit must be set */
}

/* sfx_update decrements timer and unmutes when expired */
void test_sfx_update_unmutes_on_expire(void) {
    sfx_play(SFX_EXPLOSION);
    uint8_t dur = sfx_def_duration(SFX_EXPLOSION);
    uint8_t i;
    /* advance to just before expiry */
    for (i = 0; i < dur - 1u; i++) sfx_update();
    /* still muted — no restore call yet */
    TEST_ASSERT_EQUAL_INT(1, hUGE_mute_channel_call_count);
    /* one more tick expires it */
    sfx_update();
    TEST_ASSERT_EQUAL_INT(2, hUGE_mute_channel_call_count);
    TEST_ASSERT_EQUAL_INT(HT_CH4, hUGE_mute_last_channel);
    TEST_ASSERT_EQUAL_INT(HT_CH_PLAY, hUGE_mute_last_mute);
    TEST_ASSERT_EQUAL_UINT8(0u, sfx_active_count());
}

/* Pool full: third sfx_play is dropped silently */
void test_sfx_pool_full_drops_silently(void) {
    sfx_play(SFX_EXPLOSION);
    sfx_play(SFX_PICKUP);
    /* reset mute count to measure only third call */
    hUGE_mute_channel_call_count = 0;
    sfx_play(SFX_EXPLOSION);  /* pool full — must be a no-op */
    TEST_ASSERT_EQUAL_INT(0, hUGE_mute_channel_call_count);
}

/* Channel shared: slot 0 expires while slot 1 still active — must NOT unmute */
void test_sfx_no_premature_unmute_when_channel_shared(void) {
    sfx_play(SFX_EXPLOSION);  /* slot 0, CH4, longer */
    /* Manually expire slot 0 faster by running update() until it expires */
    uint8_t dur0 = sfx_def_duration(SFX_EXPLOSION);
    uint8_t i;
    for (i = 0; i < dur0; i++) sfx_update();
    /* Slot 0 expired — if slot 1 was also CH4, unmute should have been skipped */
    /* This test needs slot 1 to be active on CH4 to exercise the guard */
    /* Re-init, play two CH4 SFX, advance until first expires */
    sfx_init();
    hUGE_mute_channel_call_count = 0;
    sfx_play(SFX_EXPLOSION);  /* dur=20 */
    sfx_play(SFX_PICKUP);     /* dur=10, same CH4 */
    uint8_t dur_pickup = sfx_def_duration(SFX_PICKUP);
    for (i = 0; i < dur_pickup; i++) sfx_update();
    /* SFX_PICKUP (shorter) expired; SFX_EXPLOSION still active on CH4 */
    /* Mute count: 2 (one mute each play) — unmute should NOT have been called */
    TEST_ASSERT_EQUAL_INT(2, hUGE_mute_channel_call_count);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_sfx_init_clears_pool);
    RUN_TEST(test_sfx_play_explosion_mutes_ch4);
    RUN_TEST(test_sfx_play_triggers_apu_ch4);
    RUN_TEST(test_sfx_update_unmutes_on_expire);
    RUN_TEST(test_sfx_pool_full_drops_silently);
    RUN_TEST(test_sfx_no_premature_unmute_when_channel_shared);
    return UNITY_END();
}
