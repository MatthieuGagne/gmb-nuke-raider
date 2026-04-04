#include <stdint.h>

/* Shared mock VRAM: 32x32 tile BG map */
uint8_t mock_vram[32u * 32u];

/* Counts every set_bkg_tiles call; reset by mock_vram_clear() */
int mock_set_bkg_tiles_call_count = 0;

/* Counts every load_bkg_row call; reset by mock_vram_clear() */
int mock_load_bkg_row_call_count = 0;

/* Tracks move_bkg calls for ordering tests */
int     mock_move_bkg_call_count = 0;
uint8_t mock_move_bkg_last_y     = 0;

void mock_vram_clear(void) {
    uint16_t i;
    mock_set_bkg_tiles_call_count = 0;
    mock_load_bkg_row_call_count  = 0;
    mock_move_bkg_call_count      = 0;
    mock_move_bkg_last_y          = 0;
    for (i = 0u; i < 32u * 32u; i++) mock_vram[i] = 0u;
}

void move_bkg(uint8_t x, uint8_t y) {
    (void)x;
    mock_move_bkg_call_count++;
    mock_move_bkg_last_y = y;
}

/* Writes a w×h rectangle of tiles into mock_vram, wrapping mod 32 */
void set_bkg_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                   const uint8_t *tiles) {
    uint8_t dy, dx;
    mock_set_bkg_tiles_call_count++;
    for (dy = 0u; dy < h; dy++) {
        for (dx = 0u; dx < w; dx++) {
            uint8_t vx = (uint8_t)((x + dx) & 31u);
            uint8_t vy = (uint8_t)((y + dy) & 31u);
            mock_vram[(uint16_t)vy * 32u + vx] = *tiles++;
        }
    }
}

/* Mock load_bkg_row: writes tiles into mock_vram, wrapping mod 32 */
void load_bkg_row(uint8_t vram_x, uint8_t vram_y,
                  uint8_t count, const uint8_t *tiles) {
    uint8_t i;
    mock_load_bkg_row_call_count++;
    for (i = 0u; i < count; i++) {
        uint8_t vx = (uint8_t)((vram_x + i) & 31u);
        mock_vram[(uint16_t)(vram_y & 31u) * 32u + vx] = tiles[i];
    }
}
