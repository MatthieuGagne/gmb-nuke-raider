#pragma bank 255
#include <gb/gb.h>
#include <gbdk/console.h>
#include <stdio.h>
#include "input.h"
#include "state_manager.h"
#include "state_game_over.h"
#include "state_title.h"

static void enter(void) {
    cls();
    gotoxy(4, 6);
    printf("GAME OVER");
    gotoxy(3, 10);
    printf("Press START");
}

static void update(void) {
    if (KEY_TICKED(J_START)) {
        state_replace(&state_title);
    }
}

static void go_exit(void) {
}

const State state_game_over = { enter, update, go_exit };
