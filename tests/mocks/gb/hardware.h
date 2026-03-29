#ifndef GB_HARDWARE_H
#define GB_HARDWARE_H

#include <stdint.h>

/* APU master control / volume / panning — written by music_init() */
static uint8_t NR52_REG = 0;
static uint8_t NR51_REG = 0;
static uint8_t NR50_REG = 0;

/* CH4 (Noise) registers — used by sfx.c.
 * Declared extern (not static) so sfx.c and test_sfx.c share the same variable.
 * Defined in tests/mocks/hardware_regs.c */
extern uint8_t NR41_REG;  /* sound length */
extern uint8_t NR42_REG;  /* volume envelope */
extern uint8_t NR43_REG;  /* polynomial counter */
extern uint8_t NR44_REG;  /* trigger / length enable */

/* CH1 (Tone+Sweep) registers — used by sfx.c for HEAL and UI SFX.
 * Declared extern (not static) so sfx.c and test_sfx.c share the same variable.
 * Defined in tests/mocks/hardware_regs.c */
extern uint8_t NR10_REG;  /* sweep */
extern uint8_t NR11_REG;  /* length / duty */
extern uint8_t NR12_REG;  /* volume envelope */
extern uint8_t NR13_REG;  /* frequency lo */
extern uint8_t NR14_REG;  /* trigger / frequency hi */

/* SDCC keyword — wraps a block to disable/restore interrupts.
 * In the test harness (gcc) this is a no-op: __critical { body } → { body } */
#define __critical

#endif /* GB_HARDWARE_H */
