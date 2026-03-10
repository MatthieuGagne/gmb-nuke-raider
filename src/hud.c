#pragma bank 255
#include <gb/gb.h>
#include "config.h"
#include "hud.h"

/* --- Tile index constants --- */
#define HUD_FONT_BASE  128u  /* first font tile in BG tile data — above track tiles */
#define HUD_FONT_COUNT  14u  /* tiles: 0-9 (10) + H(10) + P(11) + :(12) + space(13) */
#define HUD_TILE_H      10u
#define HUD_TILE_P      11u
#define HUD_TILE_COLON  12u
#define HUD_TILE_SPACE  13u

/* --- Font tile data (2bpp, 8x8 each, color 0 + color 3 only)
 *
 * Glyph layout: 5 pixels wide, bits 7..3, 7 rows tall, 1 blank row at bottom.
 * Each row pair: (pattern, pattern) — lo==hi for monochrome (color 3).
 *
 * Order: digits 0-9, then H, P, colon, space.
 */
/* __code places data in ROM on SDCC/GBDK; GCC ignores it via the define below */
#ifndef __code
#define __code
#endif
static const uint8_t __code hud_font_tiles[] = {
    /* 0: .###. / #...# / #...# / #...# / #...# / #...# / .###. / ..... */
    0x70,0x70, 0x88,0x88, 0x88,0x88, 0x88,0x88, 0x88,0x88, 0x88,0x88, 0x70,0x70, 0x00,0x00,
    /* 1: ..#.. / .##.. / ..#.. / ..#.. / ..#.. / ..#.. / .###. / ..... */
    0x20,0x20, 0x60,0x60, 0x20,0x20, 0x20,0x20, 0x20,0x20, 0x20,0x20, 0x70,0x70, 0x00,0x00,
    /* 2: .###. / #...# / ....# / ..##. / .#... / #.... / ##### / ..... */
    0x70,0x70, 0x88,0x88, 0x08,0x08, 0x30,0x30, 0x40,0x40, 0x80,0x80, 0xF8,0xF8, 0x00,0x00,
    /* 3: .###. / #...# / ....# / ..##. / ....# / #...# / .###. / ..... */
    0x70,0x70, 0x88,0x88, 0x08,0x08, 0x30,0x30, 0x08,0x08, 0x88,0x88, 0x70,0x70, 0x00,0x00,
    /* 4: #...# / #...# / #...# / ##### / ....# / ....# / ....# / ..... */
    0x88,0x88, 0x88,0x88, 0x88,0x88, 0xF8,0xF8, 0x08,0x08, 0x08,0x08, 0x08,0x08, 0x00,0x00,
    /* 5: ##### / #.... / #.... / ####. / ....# / ....# / .###. / ..... */
    0xF8,0xF8, 0x80,0x80, 0x80,0x80, 0xF0,0xF0, 0x08,0x08, 0x08,0x08, 0x70,0x70, 0x00,0x00,
    /* 6: .###. / #.... / #.... / ####. / #...# / #...# / .###. / ..... */
    0x70,0x70, 0x80,0x80, 0x80,0x80, 0xF0,0xF0, 0x88,0x88, 0x88,0x88, 0x70,0x70, 0x00,0x00,
    /* 7: ##### / ....# / ...#. / ...#. / ..#.. / ..#.. / ..#.. / ..... */
    0xF8,0xF8, 0x08,0x08, 0x10,0x10, 0x10,0x10, 0x20,0x20, 0x20,0x20, 0x20,0x20, 0x00,0x00,
    /* 8: .###. / #...# / #...# / .###. / #...# / #...# / .###. / ..... */
    0x70,0x70, 0x88,0x88, 0x88,0x88, 0x70,0x70, 0x88,0x88, 0x88,0x88, 0x70,0x70, 0x00,0x00,
    /* 9: .###. / #...# / #...# / .#### / ....# / #...# / .###. / ..... */
    0x70,0x70, 0x88,0x88, 0x88,0x88, 0x78,0x78, 0x08,0x08, 0x88,0x88, 0x70,0x70, 0x00,0x00,
    /* H: #...# / #...# / #...# / ##### / #...# / #...# / #...# / ..... */
    0x88,0x88, 0x88,0x88, 0x88,0x88, 0xF8,0xF8, 0x88,0x88, 0x88,0x88, 0x88,0x88, 0x00,0x00,
    /* P: ####. / #...# / #...# / ####. / #.... / #.... / #.... / ..... */
    0xF0,0xF0, 0x88,0x88, 0x88,0x88, 0xF0,0xF0, 0x80,0x80, 0x80,0x80, 0x80,0x80, 0x00,0x00,
    /* :: ..... / ..##. / ..##. / ..... / ..... / ..##. / ..##. / ..... */
    0x00,0x00, 0x30,0x30, 0x30,0x30, 0x00,0x00, 0x00,0x00, 0x30,0x30, 0x30,0x30, 0x00,0x00,
    /* ' ' (space): all zeros */
    0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00,
};

/* --- Module state --- */
static uint8_t  hud_hp;           /* current HP value */
static uint8_t  hud_frame_tick;   /* 0-59, resets each second */
static uint16_t hud_seconds;      /* total elapsed seconds */
static uint8_t  hud_dirty;        /* 1 = timer tiles need rewrite */
static uint8_t  hud_mm;           /* cached minutes for display */
static uint8_t  hud_ss;           /* cached seconds-within-minute for display */

/* --- Public API --- */

void hud_init(void) BANKED {
    static uint8_t row0[20];
    static uint8_t row1[20];
    uint8_t i;

    hud_hp         = PLAYER_HP_MAX;
    hud_frame_tick = 0u;
    hud_seconds    = 0u;
    hud_dirty      = 0u;
    hud_mm         = 0u;
    hud_ss         = 0u;

    /* Load font tile patterns into BG/Win tile data starting at tile 128 */
    set_bkg_data(HUD_FONT_BASE, HUD_FONT_COUNT, hud_font_tiles);

    /* Build row 0: HP:100 at cols 0-5, spaces at 6-14, 00:00 at cols 15-19 */
    for (i = 0u; i < 20u; i++) row0[i] = HUD_FONT_BASE + HUD_TILE_SPACE;
    row0[0]  = HUD_FONT_BASE + HUD_TILE_H;
    row0[1]  = HUD_FONT_BASE + HUD_TILE_P;
    row0[2]  = HUD_FONT_BASE + HUD_TILE_COLON;
    row0[3]  = HUD_FONT_BASE + (uint8_t)(PLAYER_HP_MAX / 100u);
    row0[4]  = HUD_FONT_BASE + (uint8_t)((PLAYER_HP_MAX / 10u) % 10u);
    row0[5]  = HUD_FONT_BASE + (uint8_t)(PLAYER_HP_MAX % 10u);
    row0[15] = HUD_FONT_BASE + 0u;             /* MM tens */
    row0[16] = HUD_FONT_BASE + 0u;             /* MM units */
    row0[17] = HUD_FONT_BASE + HUD_TILE_COLON;
    row0[18] = HUD_FONT_BASE + 0u;             /* SS tens */
    row0[19] = HUD_FONT_BASE + 0u;             /* SS units */

    /* Build blank row 1 (reserved for future use) */
    for (i = 0u; i < 20u; i++) row1[i] = HUD_FONT_BASE + HUD_TILE_SPACE;

    /* LCDC bit 6: Window tile map uses 0x9C00 (where set_win_tiles writes) */
    LCDC_REG |= LCDCF_WIN9C00;

    /* Pin window to bottom 2 tile rows: WX=7 (left edge), WY=128 (pixel row 128) */
    move_win(7u, 128u);
    SHOW_WIN;

    /* Write initial tile data to window tile map -- safe: display is OFF here */
    set_win_tiles(0u, 0u, 20u, 1u, row0);
    set_win_tiles(0u, 1u, 20u, 1u, row1);
}

void hud_update(void) BANKED {
    hud_frame_tick++;
    if (hud_frame_tick >= 60u) {
        hud_frame_tick = 0u;
        hud_seconds++;
        hud_mm = (uint8_t)(hud_seconds / 60u);
        hud_ss = (uint8_t)(hud_seconds % 60u);
        hud_dirty = 1u;
    }
}

void hud_render(void) BANKED {
    uint8_t timer[5];
    uint8_t hp_digits[3];

    if (!hud_dirty) return;

    /* Update timer tiles (cols 15-19) */
    timer[0] = HUD_FONT_BASE + (uint8_t)(hud_mm / 10u);
    timer[1] = HUD_FONT_BASE + (uint8_t)(hud_mm % 10u);
    timer[2] = HUD_FONT_BASE + HUD_TILE_COLON;
    timer[3] = HUD_FONT_BASE + (uint8_t)(hud_ss / 10u);
    timer[4] = HUD_FONT_BASE + (uint8_t)(hud_ss % 10u);
    set_win_tiles(15u, 0u, 5u, 1u, timer);

    /* Update HP digit tiles (cols 3-5) */
    hp_digits[0] = HUD_FONT_BASE + (uint8_t)(hud_hp / 100u);
    hp_digits[1] = HUD_FONT_BASE + (uint8_t)((hud_hp / 10u) % 10u);
    hp_digits[2] = HUD_FONT_BASE + (uint8_t)(hud_hp % 10u);
    set_win_tiles(3u, 0u, 3u, 1u, hp_digits);

    hud_dirty = 0u;
}

void hud_set_hp(uint8_t hp) BANKED {
    hud_hp    = hp;
    hud_dirty = 1u;
}

uint16_t hud_get_seconds(void) BANKED { return hud_seconds; }
uint8_t  hud_is_dirty(void) BANKED    { return hud_dirty;   }
