#pragma bank 255
#include <gb/gb.h>
#include "dialog.h"

/* Per-NPC WRAM state — 2 bytes × MAX_NPCS = 12 bytes total. */
typedef struct {
    uint8_t current_node;
    uint8_t flags;
} NpcState;

static NpcState npc_states[MAX_NPCS];

/* Active conversation cursor. */
static uint8_t           active_npc_id;
static const NpcDialog  *active_dialog;

void dialog_init(void) BANKED {
    uint8_t i;
    for (i = 0; i < MAX_NPCS; i++) {
        npc_states[i].current_node = 0;
        npc_states[i].flags        = 0;
    }
    active_npc_id = 0;
    active_dialog = 0;
}

void dialog_start(uint8_t npc_id, const NpcDialog *dialog) BANKED {
    active_npc_id = npc_id;
    active_dialog = dialog;
    /* current_node already holds the resume point from last conversation */
}

const char *dialog_get_text(void) BANKED {
    uint8_t node_idx = npc_states[active_npc_id].current_node;
    return active_dialog->nodes[node_idx].text;
}

uint8_t dialog_get_num_choices(void) BANKED {
    uint8_t node_idx = npc_states[active_npc_id].current_node;
    return active_dialog->nodes[node_idx].num_choices;
}

const char *dialog_get_choice(uint8_t idx) BANKED {
    uint8_t node_idx = npc_states[active_npc_id].current_node;
    return active_dialog->nodes[node_idx].choices[idx];
}

uint8_t dialog_advance(uint8_t choice_idx) BANKED {
    uint8_t npc       = active_npc_id;
    uint8_t node_idx  = npc_states[npc].current_node;
    const DialogNode *node = &active_dialog->nodes[node_idx];
    uint8_t next_idx;

    if (node->num_choices == 0) {
        next_idx = node->next[0];
    } else {
        next_idx = node->next[choice_idx];
    }

    if (next_idx == DIALOG_END) {
        npc_states[npc].current_node = 0; /* reset for next conversation */
        return 0;
    }

    npc_states[npc].current_node = next_idx;
    return 1;
}

void dialog_set_flag(uint8_t npc_id, uint8_t flag_bit) BANKED {
    npc_states[npc_id].flags |= (uint8_t)(1u << flag_bit);
}

uint8_t dialog_get_flag(uint8_t npc_id, uint8_t flag_bit) BANKED {
    return (npc_states[npc_id].flags >> flag_bit) & 1u;
}
