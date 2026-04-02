#pragma bank 255
#include "economy.h"

static uint16_t player_scrap = 0u;

void economy_init(void) BANKED {
    player_scrap = 0u;
}

void economy_add_scrap(uint16_t amount) BANKED {
    player_scrap = (uint16_t)(player_scrap + amount);
}

uint8_t economy_spend_scrap(uint16_t amount) BANKED {
    if (amount > player_scrap) return 0u;
    player_scrap = (uint16_t)(player_scrap - amount);
    return 1u;
}

uint16_t economy_get_scrap(void) BANKED {
    return player_scrap;
}
