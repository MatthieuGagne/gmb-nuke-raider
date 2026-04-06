#pragma bank 255
#include <gb/gb.h>
#include <gbdk/console.h>
#include <stdio.h>
#include "state_prerace.h"
#include "state_manager.h"
#include "state_overmap.h"
#include "state_playing.h"
#include "loadout.h"
#include "config.h"

BANKREF(state_prerace)

#define PR_ROWS        6u
#define PR_CONFIG_ROWS 4u   /* rows 0-3 are config; rows 4-5 are START/CANCEL */

static uint8_t pr_cursor;

static void pr_render(void) {
    uint8_t i;
    uint8_t vals[PR_CONFIG_ROWS];

    vals[0] = loadout_get_car();
    vals[1] = loadout_get_armor();
    vals[2] = loadout_get_weapon1();
    vals[3] = loadout_get_weapon2();

    cls();
    gotoxy(6u, 0u);
    printf("LOADOUT");

    for (i = 0u; i < PR_CONFIG_ROWS; i++) {
        gotoxy(0u, (uint8_t)(2u + i));
        printf(pr_cursor == i ? ">" : " ");
        gotoxy(2u, (uint8_t)(2u + i));
        printf(LOADOUT_FIELD_LABELS[i]);
        gotoxy(10u, (uint8_t)(2u + i));
        printf(LOADOUT_OPTION_NAMES[i][vals[i]]);
    }

    gotoxy(0u, 7u);
    printf(pr_cursor == 4u ? ">" : " ");
    gotoxy(2u, 7u);
    printf("START");

    gotoxy(0u, 8u);
    printf(pr_cursor == 5u ? ">" : " ");
    gotoxy(2u, 8u);
    printf("CANCEL");
}

static void enter(void) {
    uint8_t i;
    pr_cursor = 0u;
    for (i = 0u; i < 40u; i++) { move_sprite(i, 0u, 0u); }
    DISPLAY_OFF;
    pr_render();
    DISPLAY_ON;
}

static void update(void) {
    uint8_t joy = joypad();
    uint8_t changed = 0u;

    if (joy & J_UP) {
        if (pr_cursor > 0u) { pr_cursor--; changed = 1u; }
    } else if (joy & J_DOWN) {
        if (pr_cursor < (uint8_t)(PR_ROWS - 1u)) { pr_cursor++; changed = 1u; }
    } else if ((joy & J_LEFT) && pr_cursor < PR_CONFIG_ROWS) {
        switch (pr_cursor) {
            case 0u: loadout_cycle_car(-1);     break;
            case 1u: loadout_cycle_armor(-1);   break;
            case 2u: loadout_cycle_weapon1(-1); break;
            case 3u: loadout_cycle_weapon2(-1); break;
            default: break;
        }
        changed = 1u;
    } else if ((joy & J_RIGHT) && pr_cursor < PR_CONFIG_ROWS) {
        switch (pr_cursor) {
            case 0u: loadout_cycle_car(1);     break;
            case 1u: loadout_cycle_armor(1);   break;
            case 2u: loadout_cycle_weapon1(1); break;
            case 3u: loadout_cycle_weapon2(1); break;
            default: break;
        }
        changed = 1u;
    } else if (joy & J_A) {
        if (pr_cursor == 4u) {
            state_replace(&state_playing, BANK(state_playing));
            return;
        } else if (pr_cursor == 5u) {
            overmap_set_returning();
            state_pop();
            return;
        }
    } else if (joy & J_B) {
        overmap_set_returning();
        state_pop();
        return;
    }

    if (changed) { pr_render(); }
}

static void pr_exit(void) {}

const State state_prerace = {BANK(state_prerace), enter, update, pr_exit};
