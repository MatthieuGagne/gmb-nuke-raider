/* tests/test_sfx.c */
#include "unity.h"
#include "sfx.h"
#include "hUGEDriver.h"
#include "gb/hardware.h"

extern int hUGE_mute_channel_call_count;
extern enum hUGE_channel_t hUGE_mute_last_channel;
extern enum hUGE_mute_t    hUGE_mute_last_mute;

void setUp(void) {
    sfx_init();
    hUGE_mute_channel_call_count = 0;
    NR10_REG = 0; NR11_REG = 0; NR12_REG = 0; NR13_REG = 0; NR14_REG = 0;
    NR41_REG = 0; NR42_REG = 0; NR43_REG = 0; NR44_REG = 0;
}
void tearDown(void) {}

/* AC1: sfx_play(SFX_SHOOT) mutes CH4 and sets NR44 trigger bit */
void test_sfx_play_shoot_triggers_ch4(void) {
    sfx_play(SFX_SHOOT);
    TEST_ASSERT_EQUAL_INT(1, hUGE_mute_channel_call_count);
    TEST_ASSERT_EQUAL_INT(HT_CH4, (int)hUGE_mute_last_channel);
    TEST_ASSERT_EQUAL_INT(HT_CH_MUTE, (int)hUGE_mute_last_mute);
    TEST_ASSERT_NOT_EQUAL(0u, NR44_REG & 0x80u);
}

/* AC2: SFX_SHOOT and SFX_HIT use distinct NR43 values (audibly different timbre) */
void test_sfx_shoot_and_hit_differ_by_nr43(void) {
    uint8_t shoot_nr43;
    uint8_t hit_nr43;
    sfx_play(SFX_SHOOT);
    shoot_nr43 = NR43_REG;
    sfx_init();
    sfx_play(SFX_HIT);
    hit_nr43 = NR43_REG;
    TEST_ASSERT_NOT_EQUAL(shoot_nr43, hit_nr43);
}

/* AC3: sfx_play(SFX_HEAL) mutes CH1 and sets NR14 trigger bit */
void test_sfx_play_heal_triggers_ch1(void) {
    sfx_play(SFX_HEAL);
    TEST_ASSERT_EQUAL_INT(HT_CH1, (int)hUGE_mute_last_channel);
    TEST_ASSERT_EQUAL_INT(HT_CH_MUTE, (int)hUGE_mute_last_mute);
    TEST_ASSERT_NOT_EQUAL(0u, NR14_REG & 0x80u);
}

/* AC4: sfx_play(SFX_UI) mutes CH1 and sets NR14 trigger bit */
void test_sfx_play_ui_triggers_ch1(void) {
    sfx_play(SFX_UI);
    TEST_ASSERT_EQUAL_INT(HT_CH1, (int)hUGE_mute_last_channel);
    TEST_ASSERT_NOT_EQUAL(0u, NR14_REG & 0x80u);
}

/* AC5: sfx_play(SFX_SHOOT) mid-SFX_HIT resets CH4 timer to SHOOT duration */
void test_sfx_play_interrupts_same_channel(void) {
    uint8_t i;
    sfx_play(SFX_HIT);
    for (i = 0u; i < 5u; i++) sfx_tick();
    sfx_play(SFX_SHOOT);
    TEST_ASSERT_EQUAL_UINT8(sfx_def_duration(SFX_SHOOT), sfx_ch4_timer());
    TEST_ASSERT_EQUAL_UINT8(SFX_SHOOT, sfx_ch4_id());
}

/* AC6: CH1 and CH4 SFX play simultaneously without interfering */
void test_sfx_ch1_and_ch4_independent(void) {
    sfx_play(SFX_SHOOT);  /* CH4 */
    sfx_play(SFX_HEAL);   /* CH1 */
    TEST_ASSERT_EQUAL_INT(2, hUGE_mute_channel_call_count);
    TEST_ASSERT_NOT_EQUAL(0u, sfx_ch4_timer());
    TEST_ASSERT_NOT_EQUAL(0u, sfx_ch1_timer());
}

/* sfx_tick restores CH4 to hUGEDriver when timer expires (part of AC1) */
void test_sfx_tick_restores_ch4_on_expire(void) {
    uint8_t dur;
    uint8_t i;
    sfx_play(SFX_SHOOT);
    dur = sfx_def_duration(SFX_SHOOT);
    for (i = 0u; i < dur - 1u; i++) sfx_tick();
    TEST_ASSERT_EQUAL_INT(1, hUGE_mute_channel_call_count);  /* still muted */
    sfx_tick();
    TEST_ASSERT_EQUAL_INT(2, hUGE_mute_channel_call_count);
    TEST_ASSERT_EQUAL_INT(HT_CH4, (int)hUGE_mute_last_channel);
    TEST_ASSERT_EQUAL_INT(HT_CH_PLAY, (int)hUGE_mute_last_mute);
    TEST_ASSERT_EQUAL_UINT8(0u, sfx_ch4_timer());
}

/* sfx_tick restores CH1 to hUGEDriver when timer expires */
void test_sfx_tick_restores_ch1_on_expire(void) {
    uint8_t dur;
    uint8_t i;
    sfx_play(SFX_HEAL);
    dur = sfx_def_duration(SFX_HEAL);
    for (i = 0u; i < dur - 1u; i++) sfx_tick();
    TEST_ASSERT_EQUAL_INT(1, hUGE_mute_channel_call_count);
    sfx_tick();
    TEST_ASSERT_EQUAL_INT(2, hUGE_mute_channel_call_count);
    TEST_ASSERT_EQUAL_INT(HT_CH1, (int)hUGE_mute_last_channel);
    TEST_ASSERT_EQUAL_INT(HT_CH_PLAY, (int)hUGE_mute_last_mute);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_sfx_play_shoot_triggers_ch4);
    RUN_TEST(test_sfx_shoot_and_hit_differ_by_nr43);
    RUN_TEST(test_sfx_play_heal_triggers_ch1);
    RUN_TEST(test_sfx_play_ui_triggers_ch1);
    RUN_TEST(test_sfx_play_interrupts_same_channel);
    RUN_TEST(test_sfx_ch1_and_ch4_independent);
    RUN_TEST(test_sfx_tick_restores_ch4_on_expire);
    RUN_TEST(test_sfx_tick_restores_ch1_on_expire);
    return UNITY_END();
}
