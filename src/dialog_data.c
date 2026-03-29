// GENERATED — do not edit by hand.
// Source: assets/dialog/npcs.json
// Regenerate: make dialog_data  OR  python3 tools/dialog_to_c.py assets/dialog/npcs.json src/dialog_data.c
#pragma bank 255
#include <stddef.h>
#include "dialog_data.h"
#include "banking.h"

/* --- NPC 0: STEEVE --- */
static const char n0_0[] = "Roads. Parts. Sharp. Racer. Grease. Caps.";
static const char n0_1[] = "Da FUQ ?";
static const char n0_2[] = "The circuit is brutal. Stay sharp.";
static const char n0_3[] = "I've got parts if you've got caps.";
static const char n0_4[] = "Good luck out there.";
static const char n0_5[] = "Watch the east corner. It bites.";
static const char n0_6[] = "Come back with caps.";
static const char n0_c1_0[] = "The races";
static const char n0_c1_1[] = "Supplies";
static const char n0_c1_2[] = "TEST, TEST 2";
static const char n0_c2_0[] = "Thanks";
static const char n0_c2_1[] = "Tell me more";
static const char npc_name_steeve[] = "STEEVE";

static const DialogNode steeve_nodes[] = {
    /* 0 */ { n0_0, 0, {NULL,   NULL,   NULL}, {1, DIALOG_END, DIALOG_END} },
    /* 1 */ { n0_1, 3, {n0_c1_0,  n0_c1_1,  n0_c1_2}, {2, 3, DIALOG_END} },
    /* 2 */ { n0_2, 2, {n0_c2_0,  n0_c2_1,  NULL}, {4, 5, DIALOG_END} },
    /* 3 */ { n0_3, 0, {NULL,   NULL,   NULL}, {6, DIALOG_END, DIALOG_END} },
    /* 4 */ { n0_4, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
    /* 5 */ { n0_5, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
    /* 6 */ { n0_6, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
};

/* --- NPC 1: TRADER --- */
static const char n1_0[] = "Got caps? I've got wares.";
static const char n1_1[] = "Come back when you're loaded.";
static const char n1_c0_0[] = "Browse";
static const char n1_c0_1[] = "Leave";
static const char npc_name_trader[] = "TRADER";

static const DialogNode trader_nodes[] = {
    /* 0 */ { n1_0, 2, {n1_c0_0,  n1_c0_1,  NULL}, {1, DIALOG_END, DIALOG_END} },
    /* 1 */ { n1_1, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
};

/* --- NPC 2: DRIFTER --- */
static const char n2_0[] = "Just passing through.";
static const char n2_1[] = "Stay sharp out there.";
static const char npc_name_drifter[] = "DRIFTER";

static const DialogNode drifter_nodes[] = {
    /* 0 */ { n2_0, 0, {NULL,   NULL,   NULL}, {1, DIALOG_END, DIALOG_END} },
    /* 1 */ { n2_1, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
};

/* --- NPC 3: PLACEHOLDER3 --- */
static const char n3_0[] = "...";
static const char npc_name_placeholder3[] = "PLACEHOLDER3";

static const DialogNode placeholder3_nodes[] = {
    /* 0 */ { n3_0, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
};

/* --- NPC 4: PLACEHOLDER4 --- */
static const char n4_0[] = "...";
static const char npc_name_placeholder4[] = "PLACEHOLDER4";

static const DialogNode placeholder4_nodes[] = {
    /* 0 */ { n4_0, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
};

/* --- NPC 5: PLACEHOLDER5 --- */
static const char n5_0[] = "...";
static const char npc_name_placeholder5[] = "PLACEHOLDER5";

static const DialogNode placeholder5_nodes[] = {
    /* 0 */ { n5_0, 0, {NULL,   NULL,   NULL}, {DIALOG_END, DIALOG_END, DIALOG_END} },
};

/* --- NPC dialog table (indexed by npc_id) --- */
BANKREF(npc_dialogs)
const NpcDialog npc_dialogs[] = {
    { steeve_nodes, 7, npc_name_steeve }, /* NPC 0: STEEVE */
    { trader_nodes, 2, npc_name_trader }, /* NPC 1: TRADER */
    { drifter_nodes, 2, npc_name_drifter }, /* NPC 2: DRIFTER */
    { placeholder3_nodes, 1, npc_name_placeholder3 }, /* NPC 3: PLACEHOLDER3 */
    { placeholder4_nodes, 1, npc_name_placeholder4 }, /* NPC 4: PLACEHOLDER4 */
    { placeholder5_nodes, 1, npc_name_placeholder5 }, /* NPC 5: PLACEHOLDER5 */
};
