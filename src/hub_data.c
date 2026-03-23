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

const HubDef * const hub_table[] = { &hub0 };
const uint8_t         hub_table_count = 1u;
