#pragma bank 255
#include <gb/gb.h>
#include <gbdk/console.h>
#include <stdio.h>
#include "banking.h"
#include "input.h"
#include "state_manager.h"
#include "state_game_over.h"
#include "state_title.h"
BANKREF(state_game_over)
BANKREF_EXTERN(state_game_over)

static void enter(void) {
    DISPLAY_OFF;
    cls();
    gotoxy(4u, 6u);
    printf("GAME OVER");
    gotoxy(2u, 10u);
    printf("Press START");
    DISPLAY_ON;
}

static void update(void) {
    if (KEY_TICKED(J_START)) {
        state_replace(&state_title);
    }
}

static void go_exit(void) {}

const State state_game_over = { BANK(state_game_over), enter, update, go_exit };
