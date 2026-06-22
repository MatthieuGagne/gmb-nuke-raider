#ifndef HUB_DATA_H
#define HUB_DATA_H

#include <gb/gb.h>
#include <stdint.h>
#include "config.h"

typedef struct {
    const char *name;
    uint8_t     num_npcs;
    const char *npc_names[MAX_HUB_NPCS];
    uint8_t     npc_dialog_ids[MAX_HUB_NPCS]; /* indices into npc_dialogs[] */
} HubDef;

extern const HubDef * const hub_table[];
extern const uint8_t         hub_table_count;

/* Vendor loadout field per npc_id; 0xFF = not a vendor. Generated in hub_data.c
 * (bank 0) so bank-0 state_hub.c can read it without a bank switch. */
extern const uint8_t npc_vendor_field[];

#endif /* HUB_DATA_H */
