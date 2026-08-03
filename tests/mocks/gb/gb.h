#ifndef MOCK_GB_H
#define MOCK_GB_H

/* Mock stubs for <gb/gb.h> — host-side unit test compilation only. */

#include <stdint.h>

/* The whole of this header is mock scaffolding: several file-scope statics stand in for
 * hardware registers and are written by only some translation units, so every TU that does
 * not touch one gets -Wunused-variable under the -Wall -Wextra in TEST_FLAGS. Across 35 test
 * binaries that produced 6,877 warnings per `make test` run (#525).
 *
 * The suppression is a balanced region rather than a per-variable __attribute__((unused)) on
 * purpose: a new mock static added anywhere in the body below is inside the region by
 * construction, so the storm cannot come back through a forgotten attribute (R4). The region
 * is popped before the final #endif, so -Wall -Wextra stays fully in force for the game
 * sources and for the including test file (R2) — nothing here is a real defect, everything
 * outside it still is.
 *
 * Do not write a glob such as "src" + slash + star + ".c" in this comment: the slash-star
 * sequence trips -Wcomment once per translation unit, which is its own 1,745-line storm.
 */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-variable"
#pragma GCC diagnostic ignored "-Wunused-const-variable"
#pragma GCC diagnostic ignored "-Wunused-function"

/* SDCC ROM-placement qualifiers — noop on gcc */
#ifndef __code
#define __code
#endif
#ifndef __at
#define __at(x)
#endif

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

/* Interrupt control — no-ops in host tests */
static inline void disable_interrupts(void) {}
static inline void enable_interrupts(void) {}

/* VBlank */
static inline void wait_vbl_done(void) {}

/* Joypad — returns 0 (no buttons pressed) in tests */
static inline uint8_t joypad(void) { return 0; }

/* Sprite mode / display control */
#define SPRITES_8x8  ((void)0)
#define SHOW_SPRITES ((void)0)

/* Sprite prop flags */
#define S_FLIPX 0x20U
#define S_FLIPY 0x40U

/* Sprite functions */
static inline void set_sprite_data(uint8_t first_tile, uint8_t nb_tiles,
                                    const uint8_t *data) {
    (void)first_tile; (void)nb_tiles; (void)data;
}
/* Tracked by mock_sprites.c */
extern uint8_t mock_move_sprite_last_nb;
extern uint8_t mock_move_sprite_last_x;
extern uint8_t mock_move_sprite_last_y;
extern int     mock_move_sprite_call_count;
extern uint8_t mock_sprite_x[40];
extern uint8_t mock_sprite_y[40];
extern uint8_t mock_sprite_tile[40];
extern uint8_t mock_sprite_prop[40];
void mock_move_sprite_reset(void);
static inline void set_sprite_tile(uint8_t nb, uint8_t tile) {
    if (nb < 40u) mock_sprite_tile[nb] = tile;
}
static inline void set_sprite_prop(uint8_t nb, uint8_t prop) {
    if (nb < 40u) mock_sprite_prop[nb] = prop;
}
void move_sprite(uint8_t nb, uint8_t x, uint8_t y);

/* Background tile functions */
#define SHOW_BKG ((void)0)
#define HIDE_BKG ((void)0)

static inline void set_bkg_data(uint8_t first_tile, uint8_t nb_tiles,
                                 const uint8_t *data) {
    (void)first_tile; (void)nb_tiles; (void)data;
}
/* Declared in mock_bkg.c — linked in */
extern int     mock_move_bkg_call_count;
extern uint8_t mock_move_bkg_last_y;
void move_bkg(uint8_t x, uint8_t y);

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
extern int mock_set_bkg_tiles_call_count;
extern int mock_load_bkg_row_call_count;
/* Last set_bkg_tiles() call args — lets tests tell a row stream (w=VIS_COLS,
 * h=1) apart from a column stream (w=1, h=VIS_ROWS). */
extern uint8_t mock_bkg_last_x, mock_bkg_last_y;
extern uint8_t mock_bkg_last_w, mock_bkg_last_h;
void mock_vram_clear(void);
void set_bkg_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                   const uint8_t *tiles);
/* Implemented in mock_bkg.c — writes into mock_vram and tracks max row */
extern uint8_t mock_set_bkg_tile_xy_max_row;
extern int     mock_set_bkg_tile_xy_call_count;
void mock_set_bkg_tile_xy_reset(void);
void set_bkg_tile_xy(uint8_t x, uint8_t y, uint8_t tile);

/* ISR infrastructure mocks */
#define NONBANKED

/* Banking macros — no-ops for host-side GCC compilation */
#ifndef BANKED
#define BANKED
#endif
#define BANKREF(x)
#define BANKREF_EXTERN(x)
#define BANK(x)          0u
static uint8_t _current_bank_mock = 0;
#define CURRENT_BANK     _current_bank_mock
#define SWITCH_ROM(b)    (_current_bank_mock = (uint8_t)(b))
typedef void (*int_handler)(void);
#define VBL_IFLAG 0x01U
#define LCD_IFLAG 0x02U
static inline void add_VBL(int_handler h) { (void)h; }
static inline void add_LCD(int_handler h) { (void)h; }
static inline void set_interrupts(uint8_t flags) { (void)flags; }

/* STAT/LYC register mocks (writable by tests if needed) */
static uint8_t STAT_REG = 0;
static uint8_t LYC_REG  = 0;
#define STATF_LYC 0b01000000U

/* LCDC register — hud.c writes bit 6 (window tile map select) */
static uint8_t LCDC_REG = 0x91U; /* realistic boot value: LCD on, BG on, tile data at 0x8000 */
#define LCDCF_WIN9C00 0x40U       /* LCDC bit 6: window tile map at 0x9C00 */

/* ==== ADD NEW MOCK DECLARATIONS ABOVE THIS LINE ====
 * Anything below this pop is outside the -Wunused suppression region and re-opens the
 * 6,877-warning storm (#525 R4). */
#pragma GCC diagnostic pop

#endif /* MOCK_GB_H */
