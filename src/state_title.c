#pragma bank 255
#include <gb/gb.h>
#include <gbdk/console.h>
#include <stdio.h>
#include "input.h"
#include "state_manager.h"
#include "state_title.h"
#include "state_overmap.h"

static void enter(void) BANKED {
    cls();
    gotoxy(2, 6);
    printf("WASTELAND RACER");
    gotoxy(3, 10);
    printf("Press START");
}

static void update(void) BANKED {
    if (KEY_TICKED(J_START)) {
        state_replace(&state_overmap);
    }
}

static void st_exit(void) BANKED {
}

const State state_title = { enter, update, st_exit };
