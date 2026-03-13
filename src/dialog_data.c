#pragma bank 255
#include <stddef.h>
#include "dialog_data.h"
#include "banking.h"

/* --- NPC 0: Mechanic — 3-level branching conversation ------------------- */
/*
 * Node graph:
 *   0 (narration)  -> 1
 *   1 (2 choices)  -> 2 "The races" | 3 "Supplies"
 *   2 (2 choices)  -> 4 "Thanks"    | 5 "Tell me more"
 *   3 (narration)  -> 6
 *   4 (narration)  -> END
 *   5 (narration)  -> END
 *   6 (narration)  -> END
 */
static const char m0[] = "Greetings, racer. Ready to talk?";
static const char m1[] = "What's on your mind?";
static const char m2[] = "The circuit is brutal. Stay sharp.";
static const char m3[] = "I've got parts if you've got caps.";
static const char m4[] = "Good luck out there.";
static const char m5[] = "Watch the east corner. It bites.";
static const char m6[] = "Come back with caps.";

static const char mc1_0[] = "The races";
static const char mc1_1[] = "Supplies";
static const char mc2_0[] = "Thanks";
static const char mc2_1[] = "Tell me more";

static const DialogNode mechanic_nodes[] = {
    /* 0 */ { m0, 0, {NULL,   NULL,   NULL}, {1,          DIALOG_END, DIALOG_END} },
    /* 1 */ { m1, 2, {mc1_0,  mc1_1,  NULL}, {2,          3,          DIALOG_END} },
    /* 2 */ { m2, 2, {mc2_0,  mc2_1,  NULL}, {4,          5,          DIALOG_END} },
    /* 3 */ { m3, 0, {NULL,   NULL,   NULL}, {6,          DIALOG_END, DIALOG_END} },
    /* 4 */ { m4, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
    /* 5 */ { m5, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
    /* 6 */ { m6, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
};

/* NPC 1: Trader */
static const char t0[] = "Got caps? I've got wares.";
static const char t1[] = "Come back when you're loaded.";
static const char tc0[] = "Browse";
static const char tc1[] = "Leave";
static const DialogNode trader_nodes[] = {
    { t0, 2, {tc0,  tc1,  NULL}, {1,          DIALOG_END, DIALOG_END} },
    { t1, 0, {NULL, NULL, NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
};

/* NPC 2: Drifter */
static const char d0[] = "Just passing through.";
static const char d1[] = "Stay sharp out there.";
static const DialogNode drifter_nodes[] = {
    { d0, 0, {NULL, NULL, NULL}, {1,          DIALOG_END, DIALOG_END} },
    { d1, 0, {NULL, NULL, NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
};

static const char npc_name_mechanic[] = "MECHANIC";
static const char npc_name_trader[]   = "TRADER";
static const char npc_name_drifter[]  = "DRIFTER";

/* --- NPC dialog table (indexed by npc_id) ------------------------------- */
BANKREF(npc_dialogs)
const NpcDialog npc_dialogs[] = {
    { mechanic_nodes, 7, npc_name_mechanic }, /* NPC 0: Mechanic   */
    { trader_nodes,   2, npc_name_trader   }, /* NPC 1: Trader     */
    { drifter_nodes,  2, npc_name_drifter  }, /* NPC 2: Drifter    */
    { mechanic_nodes, 7, npc_name_mechanic }, /* NPC 3: placeholder */
    { mechanic_nodes, 7, npc_name_mechanic }, /* NPC 4: placeholder */
    { mechanic_nodes, 7, npc_name_mechanic }, /* NPC 5: placeholder */
};
