#ifndef DIALOG_DATA_H
#define DIALOG_DATA_H

#include "dialog.h"
#include "banking.h"

/* Sample NPC dialog tree — 3-level branching conversation.
 * Index into this array with an npc_id to retrieve the NpcDialog. */
extern const NpcDialog npc_dialogs[];
BANKREF_EXTERN(npc_dialogs)

#endif /* DIALOG_DATA_H */
