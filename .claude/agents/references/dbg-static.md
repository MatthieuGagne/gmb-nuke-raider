# DBG_STATIC — reading file-scope `static` variables

SDCC does not export `static` symbols to the link map, so a file-scope `static` WRAM variable is
invisible to the debuggers. `DBG_STATIC` (`src/debug.h:4-29`, #588 R3) solves this: the macro is
`static` in a release build and empty in a debug build, and **every mutable file-scope declaration
in `src/*.c` uses it**.

To resolve a file-scope variable:

1. `make build-debug`
2. Read the address from `build/debug/nuke-raider.noi` (or `build/debug/nuke-raider.map`).
3. If the variable is not there, it still carries a bare `static` — run
   `python tools/dbg_static_lint.py`, which flags exactly that, and convert it to `DBG_STATIC`.

`DBG_STATIC` does **not** apply to `static` functions (stripping those breaks the link) or to
`static const` data (it lives in ROM; the symbol readers accept WRAM addresses only).
