#ifndef DEBUG_H
#define DEBUG_H

/* DBG_STATIC — visibility, not behaviour (#588 R3).
 *
 * `static` in a release ROM, empty in a debug ROM. A file-scope variable that
 * keeps the bare `static` keyword reaches neither the .noi symbol file nor the
 * link map, so the headless smoketest cannot watch it or assert on it. Every
 * MUTABLE file-scope data declaration in src/*.c uses this macro.
 *
 * It does NOT apply to:
 *   - static functions. `update` and `enter` each occur 7 times in src/, so
 *     stripping `static` from functions breaks the link (R4).
 *   - `static const` data. It sits in ROM, and the symbol reader accepts WRAM
 *     addresses only (R5). A mutable POINTER to const data is not const data.
 *
 * SDCC gives a file-scope variable the same area and the same address whether
 * it is static or not, and the access code is identical, so the two ROMs hold
 * the same bytes. tests/test_rom_parity.py checks that.
 */
#ifdef DEBUG
  #define DBG_STATIC
#else
  #define DBG_STATIC static
#endif

/* The emitting diagnostics live behind DEBUG_TRACE, not behind DEBUG.
 * DEBUG must not add one instruction to the ROM (AC2); these macros do add
 * instructions, so they need their own flag. Build them with:
 *     make build-debug DEBUG_TRACE=1
 */
#ifdef DEBUG_TRACE
  #include <gbdk/emu_debug.h>
  #include "config.h"

  #ifdef __SDCC
  /* Internal write: appends string s to the WRAM ring buffer at DEBUG_LOG_ADDR.
   * Only active on SDCC/GBC — host tests use the no-op stub below. */
  static void dbg_write(const char *s) {
      uint8_t idx = *(volatile uint8_t *)DEBUG_LOG_IDX;
      while (*s) {
          ((volatile uint8_t *)DEBUG_LOG_ADDR)[idx % DEBUG_LOG_SIZE] = (uint8_t)*s++;
          idx = (uint8_t)((idx + 1U) % DEBUG_LOG_SIZE);
      }
      *(volatile uint8_t *)DEBUG_LOG_IDX = idx;
  }
  /* Increment the music_tick() call counter in WRAM */
  #define DBG_TICK_INC() \
      do { \
          (*(volatile uint8_t *)DEBUG_TICK_ADDR)++; \
      } while (0)
  #else
  /* Host/GCC: WRAM addresses don't exist — no-op stubs for unit tests */
  static void dbg_write(const char *s) { (void)s; }
  #define DBG_TICK_INC()  do {} while (0)
  #endif

  /* Log a labeled integer value to Emulicious console */
  #define DBG_INT(label, val) \
      do { \
          EMU_printf(label ": %d\n", (int)(val)); \
      } while (0)

  /* Log a plain string to Emulicious console AND WRAM ring buffer */
  #define DBG_STR(s) \
      do { \
          EMU_printf("%s\n", (s)); \
          dbg_write(s); \
          dbg_write("\n"); \
      } while (0)

#else
  #define DBG_INT(label, val)  do {} while (0)
  #define DBG_STR(s)           do {} while (0)
  #define DBG_TICK_INC()       do {} while (0)
#endif

/* ---- The test command mailbox (#590) ---------------------------------------
 *
 * Debug ROM only. The Makefile defines DEBUG_MAILBOX for `make build-debug` and for the host
 * test flags; the release ROM defines neither, and src/debug.c then compiles to nothing.
 *
 * The wire, nine bytes at DBG_MB_BASE:
 *
 *   +0 ready    DBG_MB_READY_VALUE once debug_mailbox_start() has run (R10)
 *   +1 opcode   0 = empty. The harness writes this LAST (R7)
 *   +2 arg0
 *   +3 arg1
 *   +4 commit   DBG_MB_SEED ^ opcode ^ arg0 ^ arg1 (R7)
 *   +5 outcome  DBG_OUT_*
 *   +6 detail   command-specific
 *   +7 epoch    incremented LAST, after outcome and detail (R9)
 *   +8 torn     commit-byte mismatches (R8)
 *
 * The addresses are fixed, not linker-allocated (R11). The debug ROM links with
 * -Wl-g.STACK=0xDF00 so the stack cannot reach them (R12).
 *
 * The block carries its own guard: tests/test_debug.c re-includes this header inside a
 * function body, and a second expansion would put the enum and the typedefs in block scope.
 */
#if defined(DEBUG_MAILBOX) && !defined(DBG_MAILBOX_DECLARED)
#define DBG_MAILBOX_DECLARED

#include <stdint.h>
#include <gb/gb.h>          /* BANKED */
#include "state_manager.h"  /* State, for the forced-transition table */

#define DBG_MB_BASE          0xDF70
#define DBG_MB_SIZE          9
#define DBG_MB_READY_VALUE   0xA5
#define DBG_MB_SEED          0x5A

#define DBG_MB_OFF_READY     0
#define DBG_MB_OFF_OPCODE    1
#define DBG_MB_OFF_ARG0      2
#define DBG_MB_OFF_ARG1      3
#define DBG_MB_OFF_COMMIT    4
#define DBG_MB_OFF_OUTCOME   5
#define DBG_MB_OFF_DETAIL    6
#define DBG_MB_OFF_EPOCH     7
#define DBG_MB_OFF_TORN      8

/* Outcome codes. C holds no message text — tools/debug_protocol.py owns every message (R21). */
#define DBG_OUT_OK           0
#define DBG_OUT_UNKNOWN_OP   1   /* detail = the opcode                       */
#define DBG_OUT_ARG_RANGE    2   /* detail = the index of the bad argument    */
#define DBG_OUT_LOCKED       3   /* detail = the loadout field                */
#define DBG_OUT_IN_RACE      4   /* detail = 0                                */
#define DBG_OUT_STACK_FULL   5   /* detail = the stack depth                  */
#define DBG_OUT_UNSUPPORTED  6   /* detail = the opcode                       */
#define DBG_OUT_POOL_FULL    7   /* detail = 0                                */
#define DBG_OUT_NO_EFFECT    8   /* detail = the value the game kept          */
#define DBG_OUT_NOT_ACTIVE   9   /* detail = the slot                         */

/* The index a FORCE_STATE argument uses for the racing state. Keep in step with
 * DBG_STATES[] in src/debug.c and STATES in tools/debug_protocol.py. */
#define DBG_STATE_PLAYING    4
#define DBG_STATE_COUNT      7

/* The opcode enum, generated from the one file that names an opcode (R13). */
#define DBG_CMD(name, opcode, argc, a0, a1) DBG_OP_##name = (opcode),
enum {
    DBG_OP_NONE = 0,
#include "debug_cmds.def"
    DBG_OP__LAST
};
#undef DBG_CMD

typedef struct {
    uint8_t opcode;
    uint8_t argc;
    uint8_t arg0_max;
    uint8_t arg1_max;
} DbgCmdSpec;

extern const DbgCmdSpec dbg_cmd_table[];
extern const uint8_t    dbg_cmd_count;

typedef struct {
    uint8_t opcode;
    uint8_t arg0;
    uint8_t arg1;
} DbgRequest;

/* A snapshot of everything outside the request that a refusal depends on.
 * debug_decide() reads this struct, the request, and the const argument table in ROM.
 * It calls no game module and reads no mutable global, so a host test drives every
 * refusal with no emulator and no game state (R19). */
typedef struct {
    uint8_t depth;            /* state_manager_depth()                                    */
    uint8_t in_race;          /* 1 when the top of the stack is the racing state           */
    uint8_t option_unlocked;  /* loadout_is_option_unlocked(arg0, arg1) for SET_OPTION;
                                 1 for every other command                                 */
} DbgEnv;

uint8_t debug_decide(const DbgRequest *req, const DbgEnv *env);

void    debug_mailbox_start(void) BANKED;
void    debug_mailbox_poll(void) BANKED;

/* Wire access. A host test reads and writes ordinary storage; the ROM reads and writes
 * DBG_MB_BASE. Both go through these two functions, so the test drives the real code. */
uint8_t debug_mb_read(uint8_t offset);
void    debug_mb_write(uint8_t offset, uint8_t value);

#ifndef __SDCC
/* Host-only seams. The ROM calls the real functions directly, because a BANKED function in a
 * struct field makes SDCC emit a broken double dereference (.claude/agents/gbdk-expert.md:123).
 * These exist in the gcc test build only, so no ROM carries an indirect call. */
typedef struct {
    uint8_t (*spawn)(uint8_t tx, uint8_t ty);
    uint8_t (*despawn)(uint8_t slot);
} DbgEnemyOps;

void debug_set_enemy_ops(const DbgEnemyOps *ops);   /* 0 restores the real ones */
void debug_set_state_table(const State *const *states, uint8_t count);  /* 0 restores */
#endif /* !__SDCC */

#endif /* DEBUG_MAILBOX && !DBG_MAILBOX_DECLARED */

#endif /* DEBUG_H */
