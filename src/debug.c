/* src/debug.c — the test command mailbox (#590). Debug ROM only. */
#ifdef DEBUG_MAILBOX
#pragma bank 30

#include <stdint.h>
#include "debug.h"
#include "config.h"
#include "economy.h"
#include "loadout.h"
#include "damage.h"
#include "turret.h"
#include "state_manager.h"
#include "state_title.h"
#include "state_overmap.h"
#include "state_hub.h"
#include "state_prerace.h"
#include "state_playing.h"
#include "state_results.h"
#include "state_game_over.h"

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

static uint8_t debug_run(const DbgRequest *req, uint8_t *detail);

/* The forced-transition table. Index order matches DBG_STATE_PLAYING in src/debug.h,
 * STATES in tools/debug_protocol.py, and the table in tools/scenarios/README.md.
 * Keep all four in step. */
static const State *const REAL_STATES[DBG_STATE_COUNT] = {
    &state_title, &state_overmap, &state_hub, &state_prerace,
    &state_playing, &state_results, &state_game_over
};

/* A function, not a static initializer: BANK(x) expands to a cast of a link-time symbol's
 * address, which this project only ever passes as a runtime argument (src/main.c:60). */
static uint8_t bank_for(uint8_t i) {
    switch (i) {
        case 0u: return BANK(state_title);
        case 1u: return 0u;                    /* state_overmap.c is bank 0 */
        case 2u: return 0u;                    /* state_hub.c is bank 0     */
        case 3u: return BANK(state_prerace);
        case 4u: return BANK(state_playing);
        case 5u: return BANK(state_results);
        default: return BANK(state_game_over);
    }
}

#ifdef __SDCC
/* The ROM calls the real functions directly. A BANKED function in a struct field would make
 * SDCC emit a broken double dereference (.claude/agents/gbdk-expert.md:123). */
#define DBG_SPAWN(tx, ty)   turret_spawn((tx), (ty))
#define DBG_DESPAWN(slot)   turret_despawn((slot))
#define DBG_STATE(i)        REAL_STATES[(i)]
#define DBG_STATE_LIMIT     DBG_STATE_COUNT
#else
DBG_STATIC const DbgEnemyOps *dbg_ops;            /* 0 until set; falls back to the real ones */
DBG_STATIC const State *const *dbg_states;
DBG_STATIC uint8_t dbg_state_count;

void debug_set_enemy_ops(const DbgEnemyOps *ops) { dbg_ops = ops; }

void debug_set_state_table(const State *const *states, uint8_t count) {
    dbg_states = states;
    dbg_state_count = count;
}

static uint8_t host_spawn(uint8_t tx, uint8_t ty) {
    return (dbg_ops != 0) ? dbg_ops->spawn(tx, ty) : turret_spawn(tx, ty);
}
static uint8_t host_despawn(uint8_t slot) {
    return (dbg_ops != 0) ? dbg_ops->despawn(slot) : turret_despawn(slot);
}
static const State *host_state(uint8_t i) {
    return (dbg_states != 0) ? dbg_states[i] : REAL_STATES[i];
}
#define DBG_SPAWN(tx, ty)   host_spawn((tx), (ty))
#define DBG_DESPAWN(slot)   host_despawn((slot))
#define DBG_STATE(i)        host_state((i))
#define DBG_STATE_LIMIT     DBG_STATE_COUNT
#endif

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

static void snapshot(const DbgRequest *req, DbgEnv *env) {
    env->depth = state_manager_depth();
    env->in_race =
        (state_manager_top() == DBG_STATE(DBG_STATE_PLAYING)) ? 1u : 0u;
    env->option_unlocked =
        (req->opcode == DBG_OP_SET_OPTION)
        ? loadout_is_option_unlocked(req->arg0, req->arg1)   /* the game's own rule */
        : 1u;
}

static void set_option(uint8_t field, uint8_t option) {
    switch (field) {
        case LOADOUT_FIELD_CAR:     loadout_set_car(option);     break;
        case LOADOUT_FIELD_ARMOR:   loadout_set_armor(option);   break;
        case LOADOUT_FIELD_WEAPON1: loadout_set_weapon1(option); break;
        default:                    loadout_set_weapon2(option); break;
    }
}

static uint8_t debug_run(const DbgRequest *req, uint8_t *detail) {
    DbgEnv env;
    uint8_t verdict;
    uint8_t hp_before;

    snapshot(req, &env);
    verdict = debug_decide(req, &env);
    if (verdict != DBG_OUT_OK) {
        switch (verdict) {
            case DBG_OUT_UNKNOWN_OP:
            case DBG_OUT_UNSUPPORTED: *detail = req->opcode; break;
            case DBG_OUT_LOCKED:      *detail = req->arg0;   break;
            case DBG_OUT_STACK_FULL:  *detail = env.depth;   break;
            default:                  *detail = 0u;          break;
        }
        return verdict;
    }

    *detail = 0u;
    switch (req->opcode) {
        case DBG_OP_ADD_SCRAP:
            economy_add_scrap((uint16_t)req->arg0 | ((uint16_t)req->arg1 << 8));
            break;
        case DBG_OP_UNLOCK_FIELD:
            loadout_unlock_option(req->arg0);
            break;
        case DBG_OP_SET_OPTION:
            set_option(req->arg0, req->arg1);
            break;
        case DBG_OP_DAMAGE:
            hp_before = damage_get_hp();
            damage_apply(req->arg0);
            *detail = damage_get_hp();
            if (req->arg0 > 0u && damage_get_hp() == hp_before) {
                return DBG_OUT_NO_EFFECT;   /* i-frames, or already dead */
            }
            break;
        case DBG_OP_HEAL:
            damage_heal(req->arg0);
            *detail = damage_get_hp();
            break;
        case DBG_OP_FORCE_STATE:
            if (req->arg1 == 1u) {
                state_pop();
            } else if (req->arg1 == 2u) {
                state_replace(DBG_STATE(req->arg0), bank_for(req->arg0));
            } else {
                state_push(DBG_STATE(req->arg0), bank_for(req->arg0));
            }
            *detail = state_manager_depth();
            break;
        case DBG_OP_SPAWN_TURRET:
            if (!DBG_SPAWN(req->arg0, req->arg1)) return DBG_OUT_POOL_FULL;
            break;
        case DBG_OP_DESPAWN_TURRET:
            if (!DBG_DESPAWN(req->arg0)) {
                *detail = req->arg0;
                return DBG_OUT_NOT_ACTIVE;
            }
            break;
        default:
            return DBG_OUT_UNKNOWN_OP;
    }
    return DBG_OUT_OK;
}

#else
/* The release ROM compiles this file to nothing (R1). The typedef keeps the translation unit
 * non-empty, which costs zero bytes and silences SDCC warning 190. */
typedef int debug_mailbox_not_compiled_t;
#endif /* DEBUG_MAILBOX */
