---
summary: config.h macro patterns — brace-initializer table macros vs SDCC compound-literal rejection (PLAYER_TURN_FRAMES_TABLE), #if/#error range guards (PLAYER_HANDLING), config.h is NOT a Makefile dependency so use make clean && make
tags: [config, macros, sdcc, makefile, preprocessor, lookup-table, gotcha]
---

# config.h patterns & the Makefile header-dependency gotcha

Both from #628 Task 1. Related: [[sdcc-banking-rules]] (SDCC syntax rules),
[[verification-techniques]] (prove-it-bites flip tests).

## Brace-initializer table macros compile under SDCC; compound literals do not

`#define X { 8u, 7u, ... }` consumed as `static const uint8_t T[8] = X;` compiles fine
under SDCC — do not confuse it with a compound literal. SDCC rejects
`(const uint8_t[]){...}` (an anonymous compound-literal expression) but a plain brace
initializer for a NAMED `static const` array declaration is standard aggregate init,
accepted by SDCC same as any C compiler. `src/config.h` has
`#define PLAYER_TURN_FRAMES_TABLE { 8u, 7u, 6u, 5u, 4u, 3u, 2u, 1u }` for exactly this
reason — a lookup-table macro meant to be consumed by a later
`static const uint8_t X[8] = PLAYER_TURN_FRAMES_TABLE;` declaration, sidestepping
SM83's lack of a divide instruction (handling value → turn-frame-period must be a table
lookup, never arithmetic on the handling value).

## Range-guard macros: #if/#error next to the constant, flip-verified

A range-guard macro belongs next to the constant it bounds, as a `#if`/`#error` pair —
verify it bites by flipping the value on disk, `make clean && make`, checking the exit
code AND the `#error` text, then restoring (#628 Task 1, AC6). `PLAYER_HANDLING` in
`src/config.h` is guarded by `#if (PLAYER_HANDLING) < 0 || (PLAYER_HANDLING) > 7` /
`#error "..."` right after its `#define` and the table it indexes.

**Load-bearing gotcha: `src/config.h` is NOT a Makefile dependency of any `.o`**
(`Makefile:202` is a bare pattern rule, no header deps, no `-MMD`) — a bare `make`
after editing `config.h` can relink a stale `.o` and silently skip recompilation, so
the flip-test AND any real future edit to a macro consumed by compiled code MUST use
`make clean && make`, never a bare `make`. Confirmed: flipping `PLAYER_HANDLING` to `8`
and running `make clean && make` gives exit code 2 and prints
`src/config.h:41:2: error: #error "PLAYER_HANDLING must be 0-7 ..."` to stdout/stderr;
restoring the file and rebuilding goes green again with an empty
`git status --porcelain`. (Same "only a clean build is authoritative" theme as
[[autobank-symbol-placement]].)
