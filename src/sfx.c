/* src/sfx.c — two-channel one-shot SFX: CH1 (tone sweep) + CH4 (noise).
 * Bank 0, no #pragma bank, no BANKED keyword — same constraint as music.c.
 * APU writes must not race with bank switches; this file stays in home bank.
 *
 * Design:
 *   sfx_play() writes APU registers immediately (R8) and starts the release timer.
 *   sfx_tick() decrements timers and restores hUGEDriver ownership on expiry.
 *   Last-caller wins on a given channel — new sfx_play() simply overwrites (R7). */
#include "sfx.h"
#include "hUGEDriver.h"
#include <gb/hardware.h>
#include <stdint.h>

/* SFX definition: per-channel APU register snapshot + release duration in frames.
 *
 * Field mapping by channel:
 *   CH1: nr0=NR10(sweep), nr1=NR11(duty/len), nr2=NR12(env), nr3=NR13(freq lo), nr4=NR14(trigger)
 *   CH4: nr0=unused,      nr1=NR41(len),      nr2=NR42(env), nr3=NR43(poly),    nr4=NR44(trigger)
 *
 * To add a new SFX: add a row to sfx_defs[], increment SFX_COUNT in sfx.h. */
typedef struct {
    uint8_t channel;   /* HT_CH1 or HT_CH4 cast to uint8_t */
    uint8_t nr0;
    uint8_t nr1;
    uint8_t nr2;
    uint8_t nr3;
    uint8_t nr4;
    uint8_t duration;  /* frames until hUGEDriver channel ownership is restored */
} sfx_def_t;

static const sfx_def_t sfx_defs[SFX_COUNT] = {
    /* SFX_SHOOT: CH4 short noise burst (8 frames)
     * NR42=0xF7: vol=15, env-add, pace=7 — decays quickly
     * NR43=0x77: clock-shift=7, LFSR-width=1(short), divisor=7 */
    { (uint8_t)HT_CH4, 0x00u, 0x00u, 0xF7u, 0x77u, 0x80u, 8u  },

    /* SFX_HIT: CH4 heavy noise hit (15 frames)
     * NR43=0x55: different divisor/width from SHOOT (AC2 — audibly distinct) */
    { (uint8_t)HT_CH4, 0x00u, 0x00u, 0xD3u, 0x55u, 0x80u, 15u },

    /* SFX_HEAL: CH1 rising sweep tone (20 frames)
     * NR10=0x13: pace=1, direction=up(0), step=3 — slow ascending pitch
     * NR12=0xF0: vol=15, no envelope decay
     * NR14=0xC7: trigger | length-enable | freq-hi=7 */
    { (uint8_t)HT_CH1, 0x13u, 0x80u, 0xF0u, 0x00u, 0xC7u, 20u },

    /* SFX_UI: CH1 short confirm blip (6 frames)
     * NR10=0x00: no sweep — flat tone
     * NR14=0x87: trigger | freq-hi=7 (high-pitched brief blip) */
    { (uint8_t)HT_CH1, 0x00u, 0x80u, 0xF0u, 0x00u, 0x87u, 6u  },
};

/* R9: SoA state — one timer+id pair per channel.
 * timer==0 means the channel is inactive (returned to hUGEDriver). */
static uint8_t ch1_sfx_id;
static uint8_t ch1_timer;
static uint8_t ch4_sfx_id;
static uint8_t ch4_timer;

void sfx_init(void) {
    ch1_sfx_id = SFX_COUNT;  /* SFX_COUNT = out-of-range sentinel = inactive */
    ch1_timer  = 0u;
    ch4_sfx_id = SFX_COUNT;
    ch4_timer  = 0u;
}

void sfx_play(sfx_id_t id) {
    const sfx_def_t *def;
    if (id >= SFX_COUNT) return;  /* bounds guard — bad caller drops silently */
    def = &sfx_defs[id];
    if (def->channel == (uint8_t)HT_CH4) {
        ch4_sfx_id = id;
        ch4_timer  = def->duration;
        hUGE_mute_channel(HT_CH4, HT_CH_MUTE);
        NR41_REG = def->nr1;
        NR42_REG = def->nr2;
        NR43_REG = def->nr3;
        NR44_REG = def->nr4;
    } else {  /* HT_CH1 */
        ch1_sfx_id = id;
        ch1_timer  = def->duration;
        hUGE_mute_channel(HT_CH1, HT_CH_MUTE);
        /* Writing NR10 while ch1_timer>0 intentionally restarts the sweep unit.
         * Last-caller-wins: new SFX overwrites the old tone mid-flight. */
        NR10_REG = def->nr0;
        NR11_REG = def->nr1;
        NR12_REG = def->nr2;
        NR13_REG = def->nr3;
        NR14_REG = def->nr4;
    }
}

void sfx_tick(void) {
    if (ch4_timer != 0u) {
        ch4_timer--;
        if (ch4_timer == 0u) {
            ch4_sfx_id = SFX_COUNT;
            hUGE_mute_channel(HT_CH4, HT_CH_PLAY);
        }
    }
    if (ch1_timer != 0u) {
        ch1_timer--;
        if (ch1_timer == 0u) {
            ch1_sfx_id = SFX_COUNT;
            hUGE_mute_channel(HT_CH1, HT_CH_PLAY);
        }
    }
}

/* --- Test-visible helpers ------------------------------------------------- */

uint8_t sfx_def_duration(sfx_id_t id) {
    if (id >= SFX_COUNT) return 0u;  /* bounds guard — mirrors sfx_play() */
    return sfx_defs[id].duration;
}
uint8_t sfx_ch1_timer(void)           { return ch1_timer; }
uint8_t sfx_ch4_timer(void)           { return ch4_timer; }
uint8_t sfx_ch1_id(void)             { return ch1_sfx_id; }
uint8_t sfx_ch4_id(void)             { return ch4_sfx_id; }
