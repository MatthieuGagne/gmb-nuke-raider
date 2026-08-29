# Headless WRAM Read (State Inspection)

Use when the symptom is a wrong WRAM value, not a visual glitch — faster than launching Emulicious.

## Pattern

**1. Export debug globals in `src/foo.c` alongside the static variables:**
```c
uint8_t dbg_foo_armed;
int8_t  dbg_foo_pvy;
uint8_t dbg_foo_cps;
```

**2. Find their addresses after building:**
```bash
grep "dbg_foo" build/nuke-raider.map
```
Addresses shift if WRAM layout changes — always re-grep after a new build.

**3. Read them via PyBoy:**
```python
from pyboy import PyBoy
pyboy = PyBoy('build/nuke-raider.gb', window='null')   # no cgb_mode kwarg — causes KeyError
pyboy.set_emulation_speed(0)
# ... navigate with pyboy.send_input() + pyboy.advance_frame() ...
val = pyboy.memory[0xC373]   # address from .map grep
```

**CRITICAL:** `window='null'` is the correct headless flag. Do NOT pass `cgb_mode=True` — it raises `KeyError: Unknown keyword argument`.

Combine the two: navigate with `screenshot.py` `wait_memory` steps, then read adjacent WRAM
bytes via `pyboy.memory[addr]`. For a full headless diagnosis — navigate, read, iterate
hypotheses — dispatch the `pyboy-debug` agent instead of scripting it here.
