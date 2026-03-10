#include <stdint.h>

uint8_t mock_move_sprite_last_nb    = 0;
uint8_t mock_move_sprite_last_x     = 0;
uint8_t mock_move_sprite_last_y     = 0;
int     mock_move_sprite_call_count = 0;
uint8_t mock_sprite_x[40];
uint8_t mock_sprite_y[40];

void mock_move_sprite_reset(void) {
    uint8_t i;
    mock_move_sprite_last_nb    = 0;
    mock_move_sprite_last_x     = 0;
    mock_move_sprite_last_y     = 0;
    mock_move_sprite_call_count = 0;
    for (i = 0u; i < 40u; i++) {
        mock_sprite_x[i] = 0u;
        mock_sprite_y[i] = 0u;
    }
}

void move_sprite(uint8_t nb, uint8_t x, uint8_t y) {
    mock_move_sprite_last_nb = nb;
    mock_move_sprite_last_x  = x;
    mock_move_sprite_last_y  = y;
    mock_move_sprite_call_count++;
    if (nb < 40u) {
        mock_sprite_x[nb] = x;
        mock_sprite_y[nb] = y;
    }
}
