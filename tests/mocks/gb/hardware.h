#ifndef GB_HARDWARE_H
#define GB_HARDWARE_H

#include <stdint.h>

/* APU master control / volume / panning — written by music_init() */
static uint8_t NR52_REG = 0;
static uint8_t NR51_REG = 0;
static uint8_t NR50_REG = 0;

/* CH4 (Noise) registers — used by sfx.c */
static uint8_t NR41_REG = 0;  /* sound length */
static uint8_t NR42_REG = 0;  /* volume envelope */
static uint8_t NR43_REG = 0;  /* polynomial counter */
static uint8_t NR44_REG = 0;  /* trigger / length enable */

/* SDCC keyword — wraps a block to disable/restore interrupts.
 * In the test harness (gcc) this is a no-op: __critical { body } → { body } */
#define __critical

#endif /* GB_HARDWARE_H */
