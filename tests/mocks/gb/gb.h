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

/* Sprite mode / display control */
#define SPRITES_8x8  ((void)0)
#define SHOW_SPRITES ((void)0)

/* Sprite functions */
static inline void set_sprite_data(uint8_t first_tile, uint8_t nb_tiles,
                                    const uint8_t *data) {
    (void)first_tile; (void)nb_tiles; (void)data;
}
static inline void set_sprite_tile(uint8_t nb, uint8_t tile) {
    (void)nb; (void)tile;
}
static inline void move_sprite(uint8_t nb, uint8_t x, uint8_t y) {
    (void)nb; (void)x; (void)y;
}

/* Background tile functions */
#define SHOW_BKG ((void)0)
#define HIDE_BKG ((void)0)

static inline void set_bkg_data(uint8_t first_tile, uint8_t nb_tiles,
                                 const uint8_t *data) {
    (void)first_tile; (void)nb_tiles; (void)data;
}
static inline void move_bkg(uint8_t x, uint8_t y) { (void)x; (void)y; }

/* Window layer stubs */
#define SHOW_WIN    ((void)0)
#define HIDE_WIN    ((void)0)
static inline void move_win(uint8_t x, uint8_t y) { (void)x; (void)y; }
static inline void set_win_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                                  const uint8_t *tiles) {
    (void)x; (void)y; (void)w; (void)h; (void)tiles;
}

/* Mock VRAM: 32x32 tile BG map, shared across TUs via mock_bkg.c */
extern uint8_t mock_vram[32u * 32u];
void mock_vram_clear(void);
void set_bkg_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                   const uint8_t *tiles);

#endif /* MOCK_GB_H */
