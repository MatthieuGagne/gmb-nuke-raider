#ifndef MOCK_CGB_H
#define MOCK_CGB_H

/* Mock stubs for <gb/cgb.h> — host-side unit test compilation only. */

#include <stdint.h>

/* CPU type detection */
#define DMG_TYPE 0x01u
#define CGB_TYPE 0x11u

extern uint8_t _cpu;  /* set to DMG_TYPE in test runner */

/* Palette functions — no-ops in tests */
static inline void set_bkg_palette(uint8_t first_palette, uint8_t nb_palettes,
                                    const uint16_t *rgb_data) {
    (void)first_palette; (void)nb_palettes; (void)rgb_data;
}

static inline void set_sprite_palette(uint8_t first_palette, uint8_t nb_palettes,
                                       const uint16_t *rgb_data) {
    (void)first_palette; (void)nb_palettes; (void)rgb_data;
}

/* RGB macro matching GBDK definition */
#ifndef RGB
#define RGB(r, g, b) ((uint16_t)((r) | ((g) << 5) | ((b) << 10)))
#endif

#endif /* MOCK_CGB_H */
