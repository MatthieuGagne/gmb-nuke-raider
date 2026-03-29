# Headless Emulator Debugging — Design Doc

**Date:** 2026-03-28
**Status:** Approved
**Scope:** Option B — PyBoy + thin GameSession harness (no CI integration)
**Follow-up:** Option C (CI + skill update) tracked as a separate GitHub issue.

---

## Problem

All runtime debugging requires a human to launch Emulicious, navigate to the buggy state, and interpret the output. Claude cannot autonomously reproduce a bug, observe runtime state, iterate on a fix, and verify the result without human intervention at every step.

---

## Goal

Give Claude a Python-scriptable interface to the ROM that enables:

1. Booting the ROM headlessly
2. Simulating button inputs to reach any game state
3. Reading WRAM values at known addresses
4. Capturing screenshots (Claude reads them via vision)
5. Reading debug log output written by `DBG_INT`/`DBG_STR`

---

## Architecture

Three independent pieces:

### 1. `debug.h` — WRAM ring buffer extension

When `DEBUG=1`, `DBG_INT` and `DBG_STR` write to a fixed WRAM ring buffer in addition to calling `EMU_printf`. When `DEBUG=0`, all macros remain no-ops — zero runtime cost.

**Layout (defined in `config.h`):**

```c
#define DEBUG_LOG_ADDR   0xC000   // start of ring buffer (64 bytes of content)
#define DEBUG_LOG_SIZE   64
#define DEBUG_LOG_IDX    0xC040   // 1 byte: current write index (wraps at 64)
```

The actual address must be verified against `memory_check.py` output to avoid WRAM collisions. Adjust in `config.h` if needed.

**Internal write function (compiled only with `DEBUG=1`):**

```c
static void dbg_write(const char *s) {
    uint8_t idx = *(volatile uint8_t*)DEBUG_LOG_IDX;
    while (*s) {
        ((volatile uint8_t*)DEBUG_LOG_ADDR)[idx % DEBUG_LOG_SIZE] = *s++;
        idx = (idx + 1) % DEBUG_LOG_SIZE;
    }
    *(volatile uint8_t*)DEBUG_LOG_IDX = idx;
}
```

`DBG_STR(s)` calls `EMU_printf` then `dbg_write(s)`.
`DBG_INT(label, val)` formats into a small stack buffer then calls `dbg_write`.

### 2. `tests/integration/helpers.py` — `GameSession` harness

Thin wrapper around PyBoy. Ad-hoc scripts import it; useful helpers get promoted into it over time.

```python
class GameSession:
    @staticmethod
    def boot(rom_path: str, headless: bool = True) -> "GameSession": ...

    def press(self, buttons: list[str], hold_frames: int = 1) -> None:
        """Buttons: "UP", "DOWN", "LEFT", "RIGHT", "A", "B", "START", "SELECT"."""

    def advance(self, frames: int = 1) -> None:
        """Advance emulation by N frames without input."""

    def read_wram(self, addr: int) -> int:
        """Read one byte from WRAM (0xC000–0xDFFF)."""

    def read_debug_log(self) -> list[str]:
        """Drain unread bytes from the WRAM ring buffer; return as lines."""

    def screenshot(self, path: str) -> None:
        """Save current screen as PNG. Claude reads it via vision."""

    def close(self) -> None: ...

    def __enter__(self): return self
    def __exit__(self, *_): self.close()
```

### 3. `Makefile` — `test-integration` target

```makefile
test-integration: build-debug
    python3 -m pytest tests/integration/ -v
```

`build-debug` compiles the ROM with `DEBUG=1 GBDK_HOME=/home/mathdaman/gbdk make`.
Ad-hoc scripts can also be run directly: `python3 tests/integration/my_script.py`.

### 4. `headless-debug` skill (`.claude/skills/headless-debug.md`)

Documents the autonomous debugging loop so Claude invokes it automatically during `systematic-debugging`:

1. Reproduce — write ad-hoc script, boot ROM, simulate inputs to buggy state
2. Observe — `read_debug_log()` + `screenshot()` after key frames
3. Hypothesize — form theory from log + visual + WRAM values
4. Fix — edit source, rebuild, re-run same script
5. Promote — extract reusable scenario into `helpers.py`

---

## Data Flow

```
src/debug.h (DBG_INT/DBG_STR)
    └─► EMU_printf [Emulicious sessions]
    └─► dbg_write() → WRAM ring buffer [0xC000–0xC040]
                            │
                    PyBoy memory API
                            │
                  GameSession.read_debug_log()
                            │
                     Claude reads output
```

---

## Out of Scope (Option C)

- GitHub Actions integration for `make test-integration`
- Updating `emulicious-debug` or `systematic-debugging` skills to reference headless workflow
- ROM accuracy validation between PyBoy and Emulicious

---

## File Changes

| File | Change |
|------|--------|
| `src/debug.h` | Add `dbg_write()` + WRAM writes to existing macros |
| `src/config.h` | Add `DEBUG_LOG_ADDR`, `DEBUG_LOG_SIZE`, `DEBUG_LOG_IDX` constants |
| `tests/integration/helpers.py` | New file — `GameSession` class |
| `tests/integration/__init__.py` | New file — empty, makes it a package |
| `Makefile` | Add `test-integration` and `build-debug` targets |
| `.claude/skills/headless-debug.md` | New skill — Claude's autonomous debug loop |
| `requirements.txt` (or `requirements-dev.txt`) | Add `pyboy` dependency |
