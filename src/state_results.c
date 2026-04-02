#pragma bank 255
#include <gb/gb.h>
#include <gbdk/console.h>
#include <stdio.h>
#include "banking.h"
#include "input.h"
#include "state_manager.h"
#include "state_results.h"
#include "state_overmap.h"
#include "economy.h"
BANKREF(state_results)

static uint16_t earned_this_race = 0u;

void state_results_set_earned(uint16_t amount) BANKED {
    earned_this_race = amount;
}

static void enter(void) {
    DISPLAY_OFF;
    cls();
    gotoxy(5u, 4u);
    printf("FINISH!");
    gotoxy(1u, 7u);
    printf("Earned: %u", earned_this_race);  /* %u correct: SDCC unsigned int is 16-bit on SM83 */
    gotoxy(1u, 9u);
    printf("Total:  %u", economy_get_scrap());
    gotoxy(1u, 14u);
    printf("Press A");
    DISPLAY_ON;
}

static void update(void) {
    if (KEY_TICKED(J_A)) {
        state_replace(&state_overmap);
    }
}

static void sr_exit(void) {}

const State state_results = { BANK(state_results), enter, update, sr_exit };
