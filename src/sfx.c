/* src/sfx.c — one-shot SFX: channel steal, APU write, timer-driven restore */
#pragma bank 255
#include "sfx.h"
#include "config.h"
#include "hUGEDriver.h"
#include <gb/hardware.h>
#include <stdint.h>

/* SFX definition: target channel, NR x1–x4 register values, duration in frames */
typedef struct {
    uint8_t channel;   /* hUGE_channel_t value — HT_CH4 etc. */
    uint8_t nr1;       /* NR_1 (length timer) */
    uint8_t nr2;       /* NR_2 (volume envelope) */
    uint8_t nr3;       /* NR_3 (frequency low / polynomial counter) */
    uint8_t nr4;       /* NR_4 (trigger | length enable) — bit 7 MUST be set */
    uint8_t duration;  /* frames SFX stays active (gate on channel restore) */
} sfx_def_t;

/* Static SFX table — add new SFX here; increment SFX_COUNT in sfx.h */
static const sfx_def_t sfx_defs[SFX_COUNT] = {
    /* SFX_EXPLOSION: CH4 noise burst, 20 frames */
    { HT_CH4, 0x00u, 0xF7u, 0x77u, 0x80u, 20u },
    /* SFX_PICKUP:    CH4 short tick,  10 frames */
    { HT_CH4, 0x00u, 0xF2u, 0x55u, 0x80u, 10u },
};

/* SoA pool — capacity constant in config.h */
static uint8_t sfx_active[MAX_SFX];
static uint8_t sfx_channel[MAX_SFX];  /* HW channel stolen (hUGE_channel_t value) */
static uint8_t sfx_timer[MAX_SFX];    /* frames remaining */
static uint8_t sfx_type[MAX_SFX];     /* sfx_defs[] index */

void sfx_init(void) {
    uint8_t i;
    for (i = 0u; i < MAX_SFX; i++) {
        sfx_active[i] = 0u;
    }
}

void sfx_play(uint8_t sfx_id) {
    const sfx_def_t *def;
    uint8_t i;
    if (sfx_id >= SFX_COUNT) return;  /* bounds guard — bad caller drops silently */
    def = &sfx_defs[sfx_id];          /* cache pointer — avoids repeated stride multiply */
    for (i = 0u; i < MAX_SFX; i++) {
        if (!sfx_active[i]) {
            sfx_active[i]  = 1u;
            sfx_channel[i] = def->channel;
            sfx_timer[i]   = def->duration;
            sfx_type[i]    = sfx_id;
            /* Steal channel — hUGEDriver keeps internal state but outputs nothing */
            hUGE_mute_channel((enum hUGE_channel_t)def->channel, HT_CH_MUTE);
            /* v1: all SFX target CH4 (NR41–NR44). If a future SFX targets a different
             * channel, add a dispatch switch here before expanding sfx_defs[]. */
            NR41_REG = def->nr1;
            NR42_REG = def->nr2;
            NR43_REG = def->nr3;
            NR44_REG = def->nr4;  /* bit 7 triggers the channel */
            return;
        }
    }
    /* Pool full — drop silently (no crash, no corruption) */
}

void sfx_update(void) {
    uint8_t i;
    uint8_t j;
    uint8_t ch;
    uint8_t other_active;
    for (i = 0u; i < MAX_SFX; i++) {
        if (sfx_active[i]) {
            sfx_timer[i]--;
            if (sfx_timer[i] == 0u) {
                sfx_active[i] = 0u;
                ch = sfx_channel[i];
                /* Only restore the channel if no other slot is still using it */
                other_active = 0u;
                for (j = 0u; j < MAX_SFX; j++) {
                    if (j != i && sfx_active[j] && sfx_channel[j] == ch) {
                        other_active = 1u;
                        break;
                    }
                }
                if (!other_active) {
                    hUGE_mute_channel(
                        (enum hUGE_channel_t)ch,
                        HT_CH_PLAY);
                }
            }
        }
    }
}

/* --- Test-visible helpers ------------------------------------------------- */

uint8_t sfx_active_count(void) {
    uint8_t i;
    uint8_t n = 0u;
    for (i = 0u; i < MAX_SFX; i++) {
        if (sfx_active[i]) n++;
    }
    return n;
}

uint8_t sfx_def_duration(uint8_t sfx_id) {
    return sfx_defs[sfx_id].duration;
}
