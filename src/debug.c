/* src/debug.c — the test command mailbox (#590). Debug ROM only. */
#ifdef DEBUG_MAILBOX
#pragma bank 30

#include <stdint.h>
#include "debug.h"
#include "config.h"

/* ---- the generated argument table (R13) ---------------------------------- */
/* No parens around individual fields: tests/test_debug_protocol.py's drift-check regex
 * (`\{(\d+),(\d+),(\d+),(\d+)\}`) requires bare digits (#590 AC9). Semantically identical
 * either way — parens around a lone scalar are a no-op in C. */
#define DBG_CMD(name, opcode, argc, a0, a1) {opcode, argc, a0, a1},
const DbgCmdSpec dbg_cmd_table[] = {
#include "debug_cmds.def"
};
#undef DBG_CMD

const uint8_t dbg_cmd_count =
    (uint8_t)(sizeof(dbg_cmd_table) / sizeof(dbg_cmd_table[0]));

/* ---- the wire ------------------------------------------------------------ */
#ifdef __SDCC
/* Fixed WRAM, outside the linker's allocation (R11). */
static volatile uint8_t *const dbg_mb = (volatile uint8_t *)DBG_MB_BASE;
#else
/* A host binary cannot dereference 0xDF70. Ordinary storage, same code path. */
DBG_STATIC uint8_t dbg_mb_storage[DBG_MB_SIZE];
static uint8_t *const dbg_mb = dbg_mb_storage;
#endif

uint8_t debug_mb_read(uint8_t offset) {
    return dbg_mb[offset];
}

void debug_mb_write(uint8_t offset, uint8_t value) {
    dbg_mb[offset] = value;
}

static const DbgCmdSpec *spec_for(uint8_t opcode) {
    uint8_t i;
    for (i = 0u; i < dbg_cmd_count; i++) {
        if (dbg_cmd_table[i].opcode == opcode) return &dbg_cmd_table[i];
    }
    return 0;
}

/* ---- the decision (R19) ---------------------------------------------------
 * Reads `req`, `env`, and the const argument table in ROM. The table is immutable data
 * generated from src/debug_cmds.def, not module state — R19's "reads no global" is about
 * game state that a host test cannot set, and this table is neither.
 */
uint8_t debug_decide(const DbgRequest *req, const DbgEnv *env) {
    const DbgCmdSpec *spec = spec_for(req->opcode);
    if (spec == 0) return DBG_OUT_UNKNOWN_OP;

    if (req->opcode == DBG_OP_SPAWN_RACER ||
        req->opcode == DBG_OP_SPAWN_PATROL) {
        return DBG_OUT_UNSUPPORTED;                       /* R17 */
    }
    if (spec->argc > 0u && req->arg0 > spec->arg0_max) return DBG_OUT_ARG_RANGE;
    if (spec->argc > 1u && req->arg1 > spec->arg1_max) return DBG_OUT_ARG_RANGE;

    if (req->opcode == DBG_OP_SET_OPTION) {
        if (env->in_race)          return DBG_OUT_IN_RACE;    /* R4 */
        if (!env->option_unlocked) return DBG_OUT_LOCKED;     /* R4 */
    }
    if (req->opcode == DBG_OP_UNLOCK_FIELD && env->in_race) {
        return DBG_OUT_IN_RACE;
    }
    if (req->opcode == DBG_OP_FORCE_STATE) {
        if (req->arg1 == 0u && env->depth >= STACK_MAX) return DBG_OUT_STACK_FULL; /* R5 */
        if (req->arg1 == 1u && env->depth == 0u)        return DBG_OUT_STACK_FULL;
    }
    return DBG_OUT_OK;
}

/* Replaced by the real dispatcher in Task 4. Until then every accepted command is a no-op. */
static uint8_t debug_run(const DbgRequest *req, uint8_t *detail);

/* ---- the frame poll (R6, R8, R9) ------------------------------------------ */
void debug_mailbox_start(void) BANKED {
    uint8_t i;
    for (i = 0u; i < DBG_MB_SIZE; i++) dbg_mb[i] = 0u;
    dbg_mb[DBG_MB_OFF_READY] = DBG_MB_READY_VALUE;        /* R10 */
}

void debug_mailbox_poll(void) BANKED {
    DbgRequest req;
    uint8_t detail = 0u;
    uint8_t outcome;

    req.opcode = dbg_mb[DBG_MB_OFF_OPCODE];
    if (req.opcode == DBG_OP_NONE) return;                /* R6: one at a time */

    req.arg0 = dbg_mb[DBG_MB_OFF_ARG0];
    req.arg1 = dbg_mb[DBG_MB_OFF_ARG1];

    if (dbg_mb[DBG_MB_OFF_COMMIT] !=
        (uint8_t)(DBG_MB_SEED ^ req.opcode ^ req.arg0 ^ req.arg1)) {
        dbg_mb[DBG_MB_OFF_TORN]++;                        /* R8 */
        dbg_mb[DBG_MB_OFF_OPCODE] = DBG_OP_NONE;
        return;                                           /* the next frame recovers */
    }

    outcome = debug_run(&req, &detail);

    dbg_mb[DBG_MB_OFF_OUTCOME] = outcome;
    dbg_mb[DBG_MB_OFF_DETAIL]  = detail;
    dbg_mb[DBG_MB_OFF_OPCODE]  = DBG_OP_NONE;
    dbg_mb[DBG_MB_OFF_EPOCH]++;                           /* R9: last */
}

static uint8_t debug_run(const DbgRequest *req, uint8_t *detail) {
    DbgEnv env;
    uint8_t outcome;
    env.depth = 1u; env.in_race = 0u; env.option_unlocked = 1u;
    *detail = 0u;
    outcome = debug_decide(req, &env);
    /* UNKNOWN_OP and UNSUPPORTED name themselves via detail=opcode (see debug.h
     * outcome-code comments) — that's a property of the refusal itself, not of a
     * command effect, so the stub fills it even before Task 4's real dispatcher. */
    if (outcome == DBG_OUT_UNKNOWN_OP || outcome == DBG_OUT_UNSUPPORTED) {
        *detail = req->opcode;
    }
    return outcome;
}

#else
/* The release ROM compiles this file to nothing (R1). The typedef keeps the translation unit
 * non-empty, which costs zero bytes and silences SDCC warning 190. */
typedef int debug_mailbox_not_compiled_t;
#endif /* DEBUG_MAILBOX */
