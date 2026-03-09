# Wasteland Racer

A Game Boy Color (GBC) game built with [GBDK-2020](https://github.com/gbdk-2020/gbdk-2020).

## Requirements

- [GBDK-2020](https://github.com/gbdk-2020/gbdk-2020/releases) installed at `~/gbdk`
  (or override with `GBDK_HOME=/path/to/gbdk make`)
- GNU `make`

## Build

```sh
GBDK_HOME=~/gbdk make
```

Output: `build/wasteland-racer.gb`

### Clean

```sh
make clean
```

## Running

```sh
mgba-qt build/wasteland-racer.gb
```

Or load `build/wasteland-racer.gb` in any GB/GBC emulator ([SameBoy](https://sameboy.github.io/), [Emulicious](https://emulicious.net/), [BGB](https://bgb.bircd.org/)).

## Project Structure

```
gmb-wasteland-racer/
├── src/
│   ├── main.c          # Entry point, main loop, game state machine
│   ├── player.c/.h     # Player module
│   └── config.h        # Capacity constants (MAX_ENEMIES, etc.)
├── assets/
│   ├── sprites/        # Raw sprite source files (.png, .gbr, etc.)
│   ├── tiles/          # Background tile source files
│   └── music/          # Music / sound data
├── tests/              # Unity unit tests (gcc, no hardware needed)
├── docs/plans/         # Design docs and implementation plans
├── .claude/            # Claude Code skills and agent configs
├── build/              # Compiler output (gitignored)
├── Makefile
└── README.md
```

## ROM Header Flags

| Flag | Value | Meaning |
|---|---|---|
| `-Wm-yc` | CGB compatible | Runs on DMG and GBC |
| `-Wm-yC` | CGB only | GBC exclusive (enhanced color) |
| `-Wm-yt1` | MBC1 | Memory bank controller type |
| `-Wm-yn"..."` | ROM title | Up to 11 chars in header |

To target GBC-only (for extra VRAM, palettes, etc.) swap `-Wm-yc` for `-Wm-yC` in the Makefile.
