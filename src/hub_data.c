// GENERATED — do not edit by hand.
// Source: assets/dialog/hubs.json + assets/dialog/npcs.json
// Regenerate: make dialog_data
// bank 0: always mapped, no pragma needed
#include <gb/gb.h>
#include "hub_data.h"

/* --- Hub 0: RUST TOWN --- */
static const char hub0_name[] = "RUST TOWN";
static const char hub0_npc0_name[] = "STEEVE";
static const char hub0_npc1_name[] = "TRADER";
static const char hub0_npc2_name[] = "DRIFTER";

static const HubDef hub0 = {
    hub0_name,
    3u,
    { hub0_npc0_name, hub0_npc1_name, hub0_npc2_name },
    { 0u, 1u, 2u }
};

/* --- Hub 1: JANKY CITY --- */
static const char hub1_name[] = "JANKY CITY";
static const char hub1_npc0_name[] = "PLACEHOLDER3";

static const HubDef hub1 = {
    hub1_name,
    1u,
    { hub1_npc0_name },
    { 3u }
};

/* --- Hub 2: ST-MOISE --- */
static const char hub2_name[] = "ST-MOISE";

static const HubDef hub2 = {
    hub2_name,
    0u,
    {  },
    {  }
};

const HubDef * const hub_table[] = { &hub0, &hub1, &hub2 };
const uint8_t         hub_table_count = 3u;

/* --- Vendor loadout field per npc_id (0xFF = not a vendor) --- */
const uint8_t npc_vendor_field[] = {
    LOADOUT_FIELD_ARMOR, /* NPC 0: STEEVE */
    LOADOUT_FIELD_WEAPON1, /* NPC 1: TRADER */
    LOADOUT_FIELD_WEAPON2, /* NPC 2: DRIFTER */
    0xFFu, /* NPC 3: PLACEHOLDER3 */
    0xFFu, /* NPC 4: PLACEHOLDER4 */
    0xFFu, /* NPC 5: PLACEHOLDER5 */
    0xFFu, /* NPC 6: PLACEHOLDER6 */
    0xFFu, /* NPC 7: PLACEHOLDER7 */
};
