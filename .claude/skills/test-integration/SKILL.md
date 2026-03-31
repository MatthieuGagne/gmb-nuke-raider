---
name: test-integration
description: Use this skill to run headless integration tests. Triggers during regression debugging, when any state transition or game logic changes, and as a mandatory gate in finishing-a-development-branch before the Emulicious smoketest. Boots the ROM headlessly via PyBoy through all game states.
---

Run `make test-integration`.

This builds the debug ROM (`make build-debug`) then runs `tests/integration/test_regression.py` via pytest, booting the ROM headlessly through every game state (Title → Overmap → Hub → Playing → Game Over → Title).

On success: report "Integration tests OK — all states passed".

On failure: list each failing test with name and error. Common causes:

- **ROM not found / Map file not found**: the debug ROM wasn't built — run `make build-debug` first, then retry
- **`KeyError: Symbol '_hp' not found`**: SDCC emitted a different symbol name — run `grep '_hp' build/nuke-raider.map` to find the actual name and update `test_regression.py`
- **Test hangs / timeout**: a frame budget constant is too small for a state transition — increase the relevant `_*_NAV_FRAMES` constant in `test_regression.py`
- **PyBoy import error**: run `pip install pyboy` to install the dependency
