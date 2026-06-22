#ifndef DIALOG_DATA_H
#define DIALOG_DATA_H

#include "dialog.h"
#include "banking.h"

/* Sample NPC dialog tree — 3-level branching conversation.
 * Index into this array with an npc_id to retrieve the NpcDialog. */
extern const NpcDialog npc_dialogs[];
BANKREF_EXTERN(npc_dialogs)

/* Vendor loadout field per npc_id; 0xFF = not a vendor. Generated in dialog_data.c. */
extern const uint8_t npc_vendor_field[];

#endif /* DIALOG_DATA_H */
