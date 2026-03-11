/* state_hub.c — NO #pragma bank 255: in bank 0, safe to call SET_BANK */
#include <gb/gb.h>
#include <gbdk/console.h>
#include <stdio.h>
#include "state_hub.h"
#include "hub_data.h"
#include "state_manager.h"
#include "input.h"
#include "banking.h"
#include "dialog.h"
#include "dialog_data.h"
#include "config.h"
#include "npc_mechanic_portrait.h"
#include "npc_trader_portrait.h"
#include "npc_drifter_portrait.h"

#define HUB_SUB_MENU   0u
#define HUB_SUB_DIALOG 1u

uint8_t overmap_hub_entered = 0u;

static uint8_t           sub_state;
static uint8_t           cursor;
static uint8_t           active_npc;
static uint8_t           dialog_cursor;
static const HubDef     *hub;

uint8_t hub_get_cursor(void)    { return cursor; }
uint8_t hub_get_sub_state(void) { return sub_state; }

/* ── Render helpers ─────────────────────────────────────────────────────── */

static void hub_render_menu(void) {
    uint8_t i;
    cls();
    gotoxy(1u, 0u);
    printf(hub->name);
    for (i = 0u; i < hub->num_npcs; i++) {
        gotoxy(2u, (uint8_t)(2u + i));
        printf(hub->npc_names[i]);
    }
    gotoxy(2u, (uint8_t)(2u + hub->num_npcs));
    printf("Leave");
    gotoxy(1u, (uint8_t)(2u + cursor));
    printf(">");
}

static void hub_render_dialog(void) {
    uint8_t num_choices;
    uint8_t i;
    static const uint8_t portrait_map[4] = {
        HUB_PORTRAIT_TILE_SLOT,       HUB_PORTRAIT_TILE_SLOT + 1u,
        HUB_PORTRAIT_TILE_SLOT + 2u,  HUB_PORTRAIT_TILE_SLOT + 3u
    };
    set_bkg_tiles(0u, 0u, 2u, 2u, portrait_map);
    gotoxy(3u, 2u);
    printf(dialog_get_text());
    num_choices = dialog_get_num_choices();
    if (num_choices == 0u) {
        gotoxy(1u, 4u);
        printf("[A] Continue");
    } else {
        for (i = 0u; i < num_choices; i++) {
            gotoxy(3u, (uint8_t)(4u + i));
            printf(dialog_get_choice(i));
        }
    }
}

/* ── Logic helpers ──────────────────────────────────────────────────────── */

static void load_portrait(uint8_t npc_idx) {
    wait_vbl_done();
    if (npc_idx == 0u) {
        { SET_BANK(npc_mechanic_portrait);
          set_bkg_data(HUB_PORTRAIT_TILE_SLOT, 4u, npc_mechanic_portrait);
          RESTORE_BANK(); }
    } else if (npc_idx == 1u) {
        { SET_BANK(npc_trader_portrait);
          set_bkg_data(HUB_PORTRAIT_TILE_SLOT, 4u, npc_trader_portrait);
          RESTORE_BANK(); }
    } else {
        { SET_BANK(npc_drifter_portrait);
          set_bkg_data(HUB_PORTRAIT_TILE_SLOT, 4u, npc_drifter_portrait);
          RESTORE_BANK(); }
    }
}

static void hub_start_dialog(uint8_t npc_cursor) {
    uint8_t npc_id;
    active_npc    = npc_cursor;
    dialog_cursor = 0u;
    npc_id = hub->npc_dialog_ids[npc_cursor];
    { SET_BANK(npc_dialogs);
      dialog_start(npc_id, &npc_dialogs[npc_id]);
      RESTORE_BANK(); }
    sub_state = HUB_SUB_DIALOG;
    wait_vbl_done();
    DISPLAY_OFF;
    cls();
    load_portrait(npc_cursor);
    hub_render_dialog();
    DISPLAY_ON;
}

static void update_menu(void) {
    uint8_t menu_size = (uint8_t)(hub->num_npcs + 1u);
    if (KEY_TICKED(J_UP) && cursor > 0u) {
        cursor--;
        hub_render_menu();
    } else if (KEY_TICKED(J_DOWN) && cursor < menu_size - 1u) {
        cursor++;
        hub_render_menu();
    } else if (KEY_TICKED(J_A)) {
        if (cursor == hub->num_npcs) {
            state_pop();
        } else {
            hub_start_dialog(cursor);
        }
    } else if (KEY_TICKED(J_START)) {
        state_pop();
    }
}

static void update_dialog(void) {
    uint8_t num_choices = dialog_get_num_choices();
    uint8_t more;
    if (num_choices > 0u) {
        if (KEY_TICKED(J_UP) && dialog_cursor > 0u) {
            dialog_cursor--;
            hub_render_dialog();
            return;
        }
        if (KEY_TICKED(J_DOWN) && dialog_cursor < num_choices - 1u) {
            dialog_cursor++;
            hub_render_dialog();
            return;
        }
    }
    if (KEY_TICKED(J_A) || KEY_TICKED(J_START)) {
        more = dialog_advance(dialog_cursor);
        dialog_cursor = 0u;
        if (more) {
            hub_render_dialog();
        } else {
            sub_state = HUB_SUB_MENU;
            cursor    = 0u;
            wait_vbl_done();
            DISPLAY_OFF;
            hub_render_menu();
            DISPLAY_ON;
        }
    }
}

/* ── State callbacks (no BANKED — plain function pointer in State struct) ── */

static void enter(void) {
    overmap_hub_entered = 0u;
    hub       = &rust_town;
    sub_state = HUB_SUB_MENU;
    cursor    = 0u;
    active_npc    = 0u;
    dialog_cursor = 0u;
    move_sprite(0u, 0u, 0u);
    move_sprite(1u, 0u, 0u);
    wait_vbl_done();
    DISPLAY_OFF;
    cls();
    hub_render_menu();
    DISPLAY_ON;
    SHOW_BKG;
}

static void update(void) {
    if (sub_state == HUB_SUB_MENU) { update_menu(); }
    else                            { update_dialog(); }
}

static void hub_exit(void) {}

const State state_hub = { enter, update, hub_exit };
