#include <stdint.h>

/* Shared mock VRAM: 32x32 tile BG map */
uint8_t mock_vram[32u * 32u];

void mock_vram_clear(void) {
    uint16_t i;
    for (i = 0u; i < 32u * 32u; i++) mock_vram[i] = 0u;
}

/* Writes a w×h rectangle of tiles into mock_vram, wrapping mod 32 */
void set_bkg_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                   const uint8_t *tiles) {
    uint8_t dy, dx;
    for (dy = 0u; dy < h; dy++) {
        for (dx = 0u; dx < w; dx++) {
            uint8_t vx = (uint8_t)((x + dx) & 31u);
            uint8_t vy = (uint8_t)((y + dy) & 31u);
            mock_vram[(uint16_t)vy * 32u + vx] = *tiles++;
        }
    }
}
