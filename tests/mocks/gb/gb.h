#ifndef MOCK_GB_H
#define MOCK_GB_H

/* Mock stubs for <gb/gb.h> — host-side unit test compilation only. */

#include <stdint.h>

typedef uint8_t  UBYTE;
typedef int8_t   BYTE;
typedef uint16_t UWORD;
typedef int16_t  WORD;

/* Joypad buttons */
#define J_UP     0x40u
#define J_DOWN   0x80u
#define J_LEFT   0x20u
#define J_RIGHT  0x10u
#define J_A      0x01u
#define J_B      0x02u
#define J_SELECT 0x04u
#define J_START  0x08u

/* Display control */
#define DISPLAY_ON  ((void)0)
#define DISPLAY_OFF ((void)0)

/* VBlank */
static inline void wait_vbl_done(void) {}

/* Joypad — returns 0 (no buttons pressed) in tests */
static inline uint8_t joypad(void) { return 0; }

#endif /* MOCK_GB_H */
