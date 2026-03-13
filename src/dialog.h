#ifndef DIALOG_H
#define DIALOG_H

#include <gb/gb.h>
#include <stdint.h>
#include "config.h"

/* Sentinel: used in DialogNode.next[] to mark end of conversation. */
#define DIALOG_END 0xFFu

/* ROM-side node: text, optional choices, and destination indices. */
typedef struct {
    const char *text;           /* displayed line                           */
    uint8_t     num_choices;    /* 0 = narration (auto-advance via next[0]) */
    const char *choices[3];     /* choice labels; NULL for unused slots      */
    uint8_t     next[3];        /* destination node index per choice/advance */
} DialogNode;

/* ROM-side per-NPC dialog: pointer to node array + count + NPC name. */
typedef struct {
    const DialogNode *nodes;
    uint8_t           num_nodes;
    const char       *name;      /* NPC display name, e.g. "MECHANIC" */
} NpcDialog;

/* --- Public API ---------------------------------------------------------- */

/* Zero all NPC state. Call once at game start. */
void dialog_init(void) BANKED;

/* Begin a conversation with npc_id, resuming from its stored current_node.
 * npc_id must be < MAX_NPCS. dialog must remain valid for the session. */
void dialog_start(uint8_t npc_id, const NpcDialog *dialog) BANKED;

/* Return the text of the current node (valid after dialog_start). */
const char *dialog_get_text(void) BANKED;

/* Return the number of choices on the current node (0 = narration). */
uint8_t dialog_get_num_choices(void) BANKED;

/* Return the label of choice idx (idx < dialog_get_num_choices()). */
const char *dialog_get_choice(uint8_t idx) BANKED;

/* Return the name of the active NPC (valid after dialog_start). */
const char *dialog_get_name(void) BANKED;

/* Advance the conversation.
 * For narration nodes (num_choices == 0): choice_idx is ignored.
 * For choice nodes: choice_idx selects the branch (0, 1, or 2).
 * Returns 1 if there is more dialog, 0 if the conversation has ended.
 * On end, current_node is reset to 0 for the next dialog_start. */
uint8_t dialog_advance(uint8_t choice_idx) BANKED;

/* Persistent flag API (within-session only, not saved to SRAM). */
void    dialog_set_flag(uint8_t npc_id, uint8_t flag_bit) BANKED;
uint8_t dialog_get_flag(uint8_t npc_id, uint8_t flag_bit) BANKED;

#endif /* DIALOG_H */
