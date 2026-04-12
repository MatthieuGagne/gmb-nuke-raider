/* state_hub.c — bank 0 (no #pragma bank), safe to call SET_BANK/SWITCH_ROM */
#include <gb/gb.h>
#include <gbdk/console.h>
#include <stdio.h>
#include "state_hub.h"
#include "hub_data.h"
#include "state_overmap.h"
#include "state_manager.h"
#include "input.h"
#include "banking.h"
#include "dialog.h"
#include "loader.h"
#include "config.h"
#include "music.h"
#include "sfx.h"

BANKREF(state_hub)

#define HUB_SUB_MENU   0u
#define HUB_SUB_DIALOG 1u
#define DIALOG_INNER_W 12u  /* inner text cols inside dialog box (cols 7-18) */

/* Clear only the 18 visible BG rows (0-17). cls() clears all 32 rows and
 * corrupts rows 18-31 that camera_init() does not restore, breaking the
 * track tilemap on overmap return. Must be called under DISPLAY_OFF. */
static void clear_visible_rows(void) {
    uint8_t tx, ty;
    for (ty = 0u; ty < 18u; ty++) {
        for (tx = 0u; tx < 20u; tx++) {
            set_bkg_tile_xy(tx, ty, 0x00u);
        }
    }
}

uint8_t overmap_hub_entered = 0u;

static uint8_t           sub_state;
static uint8_t           cursor;
static uint8_t           active_npc;
static uint8_t           dialog_cursor;
static const HubDef     *hub;
static uint8_t           dialog_prev_cursor;  /* last drawn cursor position for dirty update */
static uint8_t           dialog_page_start;   /* char offset of currently-shown page (0 = beginning) */
static uint8_t           dialog_next_offset;  /* return of last render_wrapped; 0 = no overflow */

static uint8_t           s_portrait_slot;     /* VRAM slot of active NPC portrait (16 tiles) */
static uint8_t           s_border_slot;       /* VRAM slot of dialog border tileset (8 tiles) */

/* portrait tile map and border tile rows — rebuilt at runtime via hub_rebuild_tile_maps() */
static uint8_t portrait_map[16];
static uint8_t portrait_top[HUB_PORTRAIT_BOX_W];
static uint8_t portrait_side[HUB_PORTRAIT_BOX_W];
static uint8_t portrait_bot[HUB_PORTRAIT_BOX_W];
static uint8_t dialog_top[HUB_DIALOG_BOX_W];
static uint8_t dialog_side[HUB_DIALOG_BOX_W];
static uint8_t dialog_bot[HUB_DIALOG_BOX_W];

static const uint8_t portrait_offsets[16] = {
    0u,4u,8u,12u, 1u,5u,9u,13u, 2u,6u,10u,14u, 3u,7u,11u,15u
};

static void hub_rebuild_tile_maps(void) {
    uint8_t i;
    uint8_t bl = s_border_slot;
    for (i = 0u; i < 16u; i++) portrait_map[i] = s_portrait_slot + portrait_offsets[i];

    portrait_top[0]=bl;    portrait_top[1]=bl+1u; portrait_top[2]=bl+1u;
    portrait_top[3]=bl+1u; portrait_top[4]=bl+1u; portrait_top[5]=bl+2u;
    portrait_side[0]=bl+3u; portrait_side[1]=0u;  portrait_side[2]=0u;
    portrait_side[3]=0u;    portrait_side[4]=0u;  portrait_side[5]=bl+4u;
    portrait_bot[0]=bl+5u; portrait_bot[1]=bl+6u; portrait_bot[2]=bl+6u;
    portrait_bot[3]=bl+6u; portrait_bot[4]=bl+6u; portrait_bot[5]=bl+7u;

    dialog_top[0] =bl;    dialog_top[13]=bl+2u;
    { uint8_t j; for (j=1u; j<13u; j++) dialog_top[j]=bl+1u; }
    dialog_side[0]=bl+3u; dialog_side[13]=bl+4u;
    { uint8_t j; for (j=1u; j<13u; j++) dialog_side[j]=0u; }
    dialog_bot[0] =bl+5u; dialog_bot[13]=bl+7u;
    { uint8_t j; for (j=1u; j<13u; j++) dialog_bot[j]=bl+6u; }
}

uint8_t hub_get_cursor(void)    { return cursor; }
uint8_t hub_get_sub_state(void) { return sub_state; }

/* ── Render helpers ─────────────────────────────────────────────────────── */

static void hub_render_menu(void) {
    uint8_t i;
    clear_visible_rows();       /* was: cls() */
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

/* Renders word-wrapped text starting at (start_col, start_row).
 * width is max chars per line. max_rows limits output rows.
 * start_char: byte offset into text to begin rendering (0 = beginning).
 * Returns 0 if all text was rendered; non-zero offset where next page starts. */
uint8_t render_wrapped(const char *text, uint8_t start_col, uint8_t start_row,
                        uint8_t width, uint8_t max_rows, uint8_t start_char) {
    static char word[20]; /* off-stack: WRAM buffer — re-entrancy via ISR
                           * is not possible here (input-driven, not ISR-driven) */
    uint8_t row        = start_row;
    uint8_t col        = start_col;
    uint8_t wi         = 0u;  /* index into current word */
    uint8_t si         = start_char;  /* index into source text */
    uint8_t line_len   = 0u;
    uint8_t word_start = start_char;  /* char offset where current word began */
    uint8_t finished   = 0u;

    while (row < start_row + max_rows) {
        char ch = text[si];
        if (ch == ' ' || ch == '\0') {
            /* try to place current word on current line */
            if (wi > 0u) {
                word[wi] = '\0';
                if (line_len + wi > width) {
                    /* word doesn't fit — wrap */
                    row++;
                    col      = start_col;
                    line_len = 0u;
                    if (row >= start_row + max_rows) break;
                }
                gotoxy(col, row);
                printf(word);
                col      += wi;
                line_len += wi;
                wi        = 0u;
                if (ch == ' ') { col++; line_len++; } /* account for space */
            }
            if (ch == '\0') { finished = 1u; break; }
            si++;
            word_start = si;  /* next word starts after this space */
        } else {
            if (wi == 0u) { word_start = si; }  /* record start of new word */
            /* accumulate character into word */
            word[wi++] = ch;
            /* force-break words longer than width */
            if (wi >= width) {
                word[wi] = '\0';
                gotoxy(col, row);
                printf(word);
                wi       = 0u;
                row++;
                col      = start_col;
                line_len = 0u;
                word_start = (uint8_t)(si + 1u);
            }
            si++;
        }
    }
    return finished ? 0u : word_start;
}

static void hub_render_dialog(void) {
    uint8_t num_choices;
    uint8_t i;
    /* portrait_map, portrait_top/side/bot, dialog_top/side/bot are module-level statics
     * populated by hub_rebuild_tile_maps() before hub_render_dialog() is called. */

    /* WRAM cache already populated by loader_dialog_cache_node — no bank switch needed. */

    /* --- Draw portrait box border (cols 0-5, rows 0-7) using BG tiles --- */
    set_bkg_tiles(0u, 0u, HUB_PORTRAIT_BOX_W, 1u, portrait_top);
    { uint8_t r;
      for (r = 1u; r <= 6u; r++) {
          set_bkg_tiles(0u, r, HUB_PORTRAIT_BOX_W, 1u, portrait_side);
      }
    }
    set_bkg_tiles(0u, 7u, HUB_PORTRAIT_BOX_W, 1u, portrait_bot);

    /* --- Draw dialog box border (cols 6-19, rows 0-7) using BG tiles --- */
    set_bkg_tiles(6u, 0u, HUB_DIALOG_BOX_W, 1u, dialog_top);
    { uint8_t r;
      for (r = 1u; r <= 6u; r++) {
          set_bkg_tiles(6u, r, HUB_DIALOG_BOX_W, 1u, dialog_side);
      }
    }
    set_bkg_tiles(6u, 7u, HUB_DIALOG_BOX_W, 1u, dialog_bot);

    /* --- Place portrait BG tiles at inner cols 1-4, rows 2-5 --- */
    set_bkg_tiles(1u, 2u, 4u, 4u, portrait_map);

    /* --- Draw NPC name at row 1, inner col 7 --- */
    gotoxy(7u, 1u);
    printf(dialog_get_name());
    printf(":");

    /* --- Word-wrap dialog text into inner cols 7-18, rows 2-6 --- */
    dialog_next_offset = render_wrapped(dialog_get_text(), 7u, 2u, DIALOG_INNER_W, 5u, dialog_page_start);

    /* --- Show or hide overflow arrow OAM sprite (OAM slot 2, screen tile (18,6)) --- */
    /* BG tile (18,6) = screen pixel (144,48); OAM coords add +8 x, +16 y */
    if (dialog_next_offset != 0u) {
        move_sprite(DIALOG_ARROW_OAM_SLOT, 152u, 64u);
    } else {
        move_sprite(DIALOG_ARROW_OAM_SLOT, 0u, 0u);
    }

    /* --- Draw choices or continue indicator (only on last page) --- */
    num_choices = dialog_get_num_choices();
    if (dialog_next_offset == 0u) {
    if (num_choices == 0u) {
        /* Narration: show > continue indicator (no key label) */
        gotoxy(0u, 9u);
        printf(">");
    } else {
        for (i = 0u; i < num_choices; i++) {
            /* WRAM cache already populated — read directly from dialog_choice_cache. */
            gotoxy(1u, (uint8_t)(9u + i));
            printf(dialog_get_choice(i));
        }
        /* Draw initial cursor */
        gotoxy(0u, (uint8_t)(9u + dialog_cursor));
        printf(">");
        dialog_prev_cursor = dialog_cursor;
    }
    } /* end if (dialog_next_offset == 0u) */
}

/* ── Logic helpers ──────────────────────────────────────────────────────── */

static void hub_start_dialog(uint8_t npc_cursor) {
    uint8_t npc_id;
    tile_asset_t portrait_asset;
    active_npc         = npc_cursor;
    dialog_cursor      = 0u;
    dialog_prev_cursor = 0u;
    dialog_page_start  = 0u;
    dialog_next_offset = 0u;
    npc_id = hub->npc_dialog_ids[npc_cursor];
    loader_dialog_cache_node(npc_id, 0u);
    dialog_start(npc_id);
    /* Resolve portrait asset slot from NPC cursor position:
     * 0=mechanic, 1=trader, 2=drifter — mirrors old load_portrait() logic. */
    if (npc_cursor == 0u) {
        portrait_asset = TILE_ASSET_NPC_MECHANIC;
    } else if (npc_cursor == 1u) {
        portrait_asset = TILE_ASSET_NPC_TRADER;
    } else {
        portrait_asset = TILE_ASSET_NPC_DRIFTER;
    }
    s_portrait_slot = loader_get_slot(portrait_asset);
    hub_rebuild_tile_maps();
    sub_state = HUB_SUB_DIALOG;
    vbl_display_off();         /* tick music + disable LCD in 1 VBlank */
    clear_visible_rows();       /* was: cls() */
    /* Tiles already in VRAM via loader_load_state() — no SET_BANK/set_bkg_data needed. */
    hub_render_dialog();
    DISPLAY_ON;
}

static void update_menu(void) {
    uint8_t menu_size = (uint8_t)(hub->num_npcs + 1u);
    if (KEY_TICKED(J_UP) && cursor > 0u) {
        gotoxy(1u, (uint8_t)(2u + cursor));     printf(" ");
        cursor--;
        gotoxy(1u, (uint8_t)(2u + cursor));     printf(">");
    } else if (KEY_TICKED(J_DOWN) && cursor < menu_size - 1u) {
        gotoxy(1u, (uint8_t)(2u + cursor));     printf(" ");
        cursor++;
        gotoxy(1u, (uint8_t)(2u + cursor));     printf(">");
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
    if (num_choices > 0u && dialog_next_offset == 0u) {
        if (KEY_TICKED(J_UP) && dialog_cursor > 0u) {
            dialog_cursor--;
            /* dirty cursor: erase old >, draw new > — 2 tile writes */
            gotoxy(0u, (uint8_t)(9u + dialog_prev_cursor)); printf(" ");
            gotoxy(0u, (uint8_t)(9u + dialog_cursor));      printf(">");
            dialog_prev_cursor = dialog_cursor;
            return;
        }
        if (KEY_TICKED(J_DOWN) && dialog_cursor < num_choices - 1u) {
            dialog_cursor++;
            gotoxy(0u, (uint8_t)(9u + dialog_prev_cursor)); printf(" ");
            gotoxy(0u, (uint8_t)(9u + dialog_cursor));      printf(">");
            dialog_prev_cursor = dialog_cursor;
            return;
        }
    }
    if (KEY_TICKED(J_A) || KEY_TICKED(J_START)) {
        sfx_play(SFX_UI);
        if (dialog_next_offset != 0u) {
            /* advance to next page */
            dialog_page_start  = dialog_next_offset;
            dialog_cursor      = 0u;
            dialog_prev_cursor = 0u;
            vbl_display_off();   /* tick music + disable LCD in 1 VBlank */
            clear_visible_rows();   /* was: cls() */
            hub_render_dialog();
            DISPLAY_ON;
        } else {
            /* last page — advance dialog node */
            more = dialog_advance(dialog_cursor);
            dialog_cursor      = 0u;
            dialog_prev_cursor = 0u;
            dialog_page_start  = 0u;
            dialog_next_offset = 0u;
            if (more) {
                vbl_display_off();   /* tick music + disable LCD in 1 VBlank */
                clear_visible_rows();   /* was: cls() */
                hub_render_dialog();
                DISPLAY_ON;
            } else {
                sub_state = HUB_SUB_MENU;
                cursor    = 0u;
                vbl_display_off();   /* tick music + disable LCD in 1 VBlank */
                hub_render_menu();
                DISPLAY_ON;
            }
        }
    }
}

/* ── State callbacks (no BANKED — plain function pointer in State struct) ── */

static void enter(void) {
    overmap_hub_entered = 0u;
    hub       = hub_table[current_hub_id];
    sub_state = HUB_SUB_MENU;
    cursor    = 0u;
    active_npc         = 0u;
    dialog_cursor      = 0u;
    dialog_prev_cursor = 0u;
    dialog_page_start  = 0u;
    dialog_next_offset = 0u;
    loader_load_state(k_hub_assets, k_hub_assets_count);
    s_border_slot = loader_get_slot(TILE_ASSET_DIALOG_BORDER);
    /* clear all 4 player OAM slots (player uses pool slots 0-3 for 2x2 grid) */
    move_sprite(0u, 0u, 0u);
    move_sprite(1u, 0u, 0u);
    move_sprite(2u, 0u, 0u);
    move_sprite(3u, 0u, 0u);
    move_sprite(DIALOG_ARROW_OAM_SLOT, 0u, 0u);
    DISPLAY_OFF;
    set_sprite_tile(DIALOG_ARROW_OAM_SLOT, loader_get_slot(TILE_ASSET_DIALOG_ARROW));
    hub_render_menu();
    DISPLAY_ON;
    SHOW_BKG;
}

static void update(void) {
    if (sub_state == HUB_SUB_MENU) { update_menu(); }
    else                            { update_dialog(); }
}

static void hub_exit(void) {
    loader_unload_state();
}

const State state_hub = { 0, enter, update, hub_exit };
