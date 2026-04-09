#pragma bank 255
#include <gb/gb.h>
#include "dialog.h"
#include "loader.h"

/* Per-NPC WRAM state — 2 bytes × MAX_NPCS = 12 bytes total. */
typedef struct {
    uint8_t current_node;
    uint8_t flags;
} NpcState;

static NpcState npc_states[MAX_NPCS];

/* Active conversation cursor. */
static uint8_t active_npc_id;

/* WRAM cache buffers — written by loader_dialog_cache_node (NONBANKED, bank 0).
 * Non-static so loader.c can write them directly via the extern declarations in dialog.h. */
char    dialog_text_cache[DIALOG_TEXT_BUF_LEN];
char    dialog_name_cache[DIALOG_NAME_BUF_LEN];
char    dialog_choice_cache[3][DIALOG_CHOICE_BUF_LEN];
uint8_t dialog_num_choices_cache;
uint8_t dialog_next_cache[3];

void dialog_init(void) BANKED {
    uint8_t i;
    for (i = 0; i < MAX_NPCS; i++) {
        npc_states[i].current_node = 0;
        npc_states[i].flags        = 0;
    }
    active_npc_id = 0;
}

void dialog_start(uint8_t npc_id) BANKED {
    active_npc_id = npc_id;
    /* current_node already holds the resume point from last conversation.
     * WRAM cache was populated by loader_dialog_cache_node() before this call. */
}

const char *dialog_get_text(void) BANKED {
    return dialog_text_cache;
}

uint8_t dialog_get_num_choices(void) BANKED {
    return dialog_num_choices_cache;
}

const char *dialog_get_name(void) BANKED {
    return dialog_name_cache;
}

const char *dialog_get_choice(uint8_t idx) BANKED {
    return dialog_choice_cache[idx];
}

uint8_t dialog_advance(uint8_t choice_idx) BANKED {
    uint8_t npc      = active_npc_id;
    uint8_t next_idx;

    if (dialog_num_choices_cache == 0u) {
        next_idx = dialog_next_cache[0];
    } else {
        next_idx = dialog_next_cache[choice_idx];
    }

    if (next_idx == DIALOG_END) {
        npc_states[npc].current_node = 0u; /* reset for next conversation */
        return 0u;
    }

    npc_states[npc].current_node = next_idx;
    /* Refresh WRAM cache for the new node.
     * loader_dialog_cache_node is NONBANKED (bank 0, fixed page) —
     * safe to call from BANKED code at any time. */
    loader_dialog_cache_node(npc, next_idx);
    return 1u;
}

void dialog_set_flag(uint8_t npc_id, uint8_t flag_bit) BANKED {
    npc_states[npc_id].flags |= (uint8_t)(1u << flag_bit);
}

uint8_t dialog_get_flag(uint8_t npc_id, uint8_t flag_bit) BANKED {
    return (npc_states[npc_id].flags >> flag_bit) & 1u;
}
