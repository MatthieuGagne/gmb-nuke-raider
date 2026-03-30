# Integration Tests — Local Run Guide

These tests boot the Game Boy ROM headlessly using [PyBoy](https://pyboy.dk/) and navigate through all game states in one session, verifying no crash within per-state frame budgets.

## Prerequisites

### 1. Install PyBoy

```bash
pip install pyboy
```

Requires Python 3.8+. If you get a SDL2 error on Linux, install `libsdl2-dev` — headless tests (`window="null"`) do not need SDL2 at runtime, only at import.

### 2. Build the debug ROM

The integration tests require a debug ROM (compiled with `DEBUG=1`), which enables the WRAM ring buffer and `EMU_printf` at `0xDF80`.

```bash
make build-debug
```

This produces `build/nuke-raider.gb` and `build/nuke-raider.map`.

## Running the tests

```bash
python3 -m pytest tests/integration/ -v
```

Or via the Makefile target (runs `make build-debug` first):

```bash
make test-integration
```

## What the tests verify

`test_regression.py::test_all_states` boots the ROM once and navigates through every game state in sequence:

| State | How entered |
|-------|-------------|
| Title | ROM boot |
| Overmap | START on title |
| Hub | UP on overmap (travels to CITY_HUB tile at col=9, row=6) |
| Playing | LEFT on overmap (travels to DEST tile at col=2, row=8) |
| Game Over | WRAM write: sets player HP to 0; next frame triggers death |
| Title | START on game over screen |

Pass criterion: no PyBoy exception raised within each state's frame budget. Total runtime target: under 60 seconds.

## Adding new tests

1. Add a new test function in `test_regression.py` that uses the `game_session` fixture.
2. If the test needs to reach a specific state, call the navigation helpers already used in `test_all_states`.
3. Keep each new test idempotent — if it changes game state, restore it before returning, as all tests share one session.

## Troubleshooting

**`ROM not found` / `Map file not found`**: Run `make build-debug` first.

**`KeyError: Symbol '_hp' not found`**: Run `grep '_hp' build/nuke-raider.map` to verify the symbol name. Update `find_wram_sym_from_map("_hp")` in the test if SDCC emitted a different name.

**Test hangs**: A frame budget is too small for a state transition. Increase the relevant `_*_NAV_FRAMES` constant in `test_regression.py`.
