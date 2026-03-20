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
#include "dialog_data.h"
#include "config.h"
#include "npc_mechanic_portrait.h"
#include "npc_trader_portrait.h"
#include "npc_drifter_portrait.h"
#include "dialog_arrow_sprite.h"
#include "dialog_border_tiles.h"

#define HUB_SUB_MENU   0u
#define HUB_SUB_DIALOG 1u
#define DIALOG_INNER_W 12u  /* inner text cols inside dialog box (cols 7-18) */

uint8_t overmap_hub_entered = 0u;

static uint8_t           sub_state;
static uint8_t           cursor;
static uint8_t           active_npc;
static uint8_t           dialog_cursor;
static const HubDef     *hub;
static char              dialog_text_buf[64]; /* WRAM — copy banked text here before printf */
static char              dialog_name_buf[16]; /* WRAM — copy banked NPC name here before printf */
static uint8_t           dialog_prev_cursor;  /* last drawn cursor position for dirty update */
static uint8_t           dialog_page_start;   /* char offset of currently-shown page (0 = beginning) */
static uint8_t           dialog_next_offset;  /* return of last render_wrapped; 0 = no overflow */

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

#define BRD_TL (HUB_BORDER_TILE_SLOT + 0u)
#define BRD_T  (HUB_BORDER_TILE_SLOT + 1u)
#define BRD_TR (HUB_BORDER_TILE_SLOT + 2u)
#define BRD_L  (HUB_BORDER_TILE_SLOT + 3u)
#define BRD_R  (HUB_BORDER_TILE_SLOT + 4u)
#define BRD_BL (HUB_BORDER_TILE_SLOT + 5u)
#define BRD_B  (HUB_BORDER_TILE_SLOT + 6u)
#define BRD_BR (HUB_BORDER_TILE_SLOT + 7u)

static void hub_render_dialog(void) {
    uint8_t num_choices;
    uint8_t i;
    /* portrait_map: corrected for column-major tile order from png_to_tiles.py.
     * Tile array index = tx*4+ty (col-major). For visual row r, col c:
     * tile index = c*4+r → VRAM slot = HUB_PORTRAIT_TILE_SLOT + c*4+r.
     * portrait_map[r*4+c] = HUB_PORTRAIT_TILE_SLOT + c*4+r */
    static const uint8_t portrait_map[16] = {
        HUB_PORTRAIT_TILE_SLOT,        HUB_PORTRAIT_TILE_SLOT + 4u,
        HUB_PORTRAIT_TILE_SLOT + 8u,   HUB_PORTRAIT_TILE_SLOT + 12u,
        HUB_PORTRAIT_TILE_SLOT + 1u,   HUB_PORTRAIT_TILE_SLOT + 5u,
        HUB_PORTRAIT_TILE_SLOT + 9u,   HUB_PORTRAIT_TILE_SLOT + 13u,
        HUB_PORTRAIT_TILE_SLOT + 2u,   HUB_PORTRAIT_TILE_SLOT + 6u,
        HUB_PORTRAIT_TILE_SLOT + 10u,  HUB_PORTRAIT_TILE_SLOT + 14u,
        HUB_PORTRAIT_TILE_SLOT + 3u,   HUB_PORTRAIT_TILE_SLOT + 7u,
        HUB_PORTRAIT_TILE_SLOT + 11u,  HUB_PORTRAIT_TILE_SLOT + 15u,
    };

    /* --- Copy banked text + name to WRAM before bank restore --- */
    { SET_BANK(npc_dialogs);
      {
          const char *src = dialog_get_text();
          uint8_t     k   = 0u;
          while (src[k] && k < (uint8_t)(sizeof(dialog_text_buf) - 1u)) {
              dialog_text_buf[k] = src[k]; k++;
          }
          dialog_text_buf[k] = '\0';
      }
      {
          const char *src = dialog_get_name();
          uint8_t     k   = 0u;
          while (src[k] && k < (uint8_t)(sizeof(dialog_name_buf) - 1u)) {
              dialog_name_buf[k] = src[k]; k++;
          }
          dialog_name_buf[k] = '\0';
      }
      RESTORE_BANK(); }

    /* portrait box border rows (6 tiles wide: cols 0-5) */
    static const uint8_t portrait_top[HUB_PORTRAIT_BOX_W]  = {BRD_TL, BRD_T,  BRD_T,  BRD_T,  BRD_T,  BRD_TR};
    static const uint8_t portrait_side[HUB_PORTRAIT_BOX_W] = {BRD_L,  0u,     0u,     0u,     0u,     BRD_R };
    static const uint8_t portrait_bot[HUB_PORTRAIT_BOX_W]  = {BRD_BL, BRD_B,  BRD_B,  BRD_B,  BRD_B,  BRD_BR};
    /* dialog box border rows (14 tiles wide: cols 6-19) */
    static const uint8_t dialog_top[HUB_DIALOG_BOX_W]  = {BRD_TL, BRD_T, BRD_T, BRD_T, BRD_T, BRD_T, BRD_T, BRD_T, BRD_T, BRD_T, BRD_T, BRD_T, BRD_T, BRD_TR};
    static const uint8_t dialog_side[HUB_DIALOG_BOX_W] = {BRD_L,  0u,    0u,    0u,    0u,    0u,    0u,    0u,    0u,    0u,    0u,    0u,    0u,    BRD_R };
    static const uint8_t dialog_bot[HUB_DIALOG_BOX_W]  = {BRD_BL, BRD_B, BRD_B, BRD_B, BRD_B, BRD_B, BRD_B, BRD_B, BRD_B, BRD_B, BRD_B, BRD_B, BRD_B, BRD_BR};

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
    printf(dialog_name_buf);
    printf(":");

    /* --- Word-wrap dialog text into inner cols 7-18, rows 2-6 --- */
    dialog_next_offset = render_wrapped(dialog_text_buf, 7u, 2u, DIALOG_INNER_W, 5u, dialog_page_start);

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
            /* Copy choice label to WRAM (banked pointer) */
            { SET_BANK(npc_dialogs);
              {
                  const char *src = dialog_get_choice(i);
                  uint8_t     k   = 0u;
                  while (src[k] && k < (uint8_t)(sizeof(dialog_text_buf) - 1u)) {
                      dialog_text_buf[k] = src[k]; k++;
                  }
                  dialog_text_buf[k] = '\0';
              }
              RESTORE_BANK(); }
            gotoxy(1u, (uint8_t)(9u + i));
            printf(dialog_text_buf);
        }
        /* Draw initial cursor */
        gotoxy(0u, (uint8_t)(9u + dialog_cursor));
        printf(">");
        dialog_prev_cursor = dialog_cursor;
    }
    } /* end if (dialog_next_offset == 0u) */
}
#undef BRD_TL
#undef BRD_T
#undef BRD_TR
#undef BRD_L
#undef BRD_R
#undef BRD_BL
#undef BRD_B
#undef BRD_BR

/* ── Logic helpers ──────────────────────────────────────────────────────── */

static void load_portrait(uint8_t npc_idx) {
    /* wait_vbl_done() removed: callers already turn DISPLAY_OFF before
     * calling here, so VRAM is freely accessible — no VBlank sync needed. */
    if (npc_idx == 0u) {
        { SET_BANK(npc_mechanic_portrait);
          set_bkg_data(HUB_PORTRAIT_TILE_SLOT, 16u, npc_mechanic_portrait);
          RESTORE_BANK(); }
    } else if (npc_idx == 1u) {
        { SET_BANK(npc_trader_portrait);
          set_bkg_data(HUB_PORTRAIT_TILE_SLOT, 16u, npc_trader_portrait);
          RESTORE_BANK(); }
    } else {
        { SET_BANK(npc_drifter_portrait);
          set_bkg_data(HUB_PORTRAIT_TILE_SLOT, 16u, npc_drifter_portrait);
          RESTORE_BANK(); }
    }
}

static void hub_start_dialog(uint8_t npc_cursor) {
    uint8_t npc_id;
    active_npc         = npc_cursor;
    dialog_cursor      = 0u;
    dialog_prev_cursor = 0u;
    dialog_page_start  = 0u;
    dialog_next_offset = 0u;
    npc_id = hub->npc_dialog_ids[npc_cursor];
    { SET_BANK(npc_dialogs);
      dialog_start(npc_id, &npc_dialogs[npc_id]);
      RESTORE_BANK(); }
    sub_state = HUB_SUB_DIALOG;
    wait_vbl_done(); /* sync to VBlank; writes complete well within ~1ms window */
    cls();
    load_portrait(npc_cursor);
    { SET_BANK(dialog_border_tiles);
      set_bkg_data(HUB_BORDER_TILE_SLOT, 8u, dialog_border_tiles);
      RESTORE_BANK(); }
    hub_render_dialog();
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
        if (dialog_next_offset != 0u) {
            /* advance to next page */
            dialog_page_start  = dialog_next_offset;
            dialog_cursor      = 0u;
            dialog_prev_cursor = 0u;
            wait_vbl_done(); /* sync to VBlank; tile-map writes fit in ~1ms window */
            cls();
            hub_render_dialog();
        } else {
            /* last page — advance dialog node */
            more = dialog_advance(dialog_cursor);
            dialog_cursor      = 0u;
            dialog_prev_cursor = 0u;
            dialog_page_start  = 0u;
            dialog_next_offset = 0u;
            if (more) {
                wait_vbl_done(); /* sync to VBlank; tile-map writes fit in ~1ms window */
                cls();
                hub_render_dialog();
            } else {
                sub_state = HUB_SUB_MENU;
                cursor    = 0u;
                wait_vbl_done(); /* sync to VBlank; tile-map writes fit in ~1ms window */
                hub_render_menu();
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
    move_sprite(0u, 0u, 0u);
    move_sprite(1u, 0u, 0u);
    move_sprite(DIALOG_ARROW_OAM_SLOT, 0u, 0u);
    wait_vbl_done();
    { SET_BANK(dialog_arrow_tile_data);
      set_sprite_data(DIALOG_ARROW_TILE_BASE, dialog_arrow_tile_data_count, dialog_arrow_tile_data);
      RESTORE_BANK(); }
    set_sprite_tile(DIALOG_ARROW_OAM_SLOT, DIALOG_ARROW_TILE_BASE);
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

const State state_hub = { 0, enter, update, hub_exit };
