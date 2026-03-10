# Wasteland Racer

A Game Boy Color (GBC) top-down racing game built with [GBDK-2020](https://github.com/gbdk-2020/gbdk-2020).

## Requirements

- [GBDK-2020](https://github.com/gbdk-2020/gbdk-2020/releases) installed at `~/gbdk`
  (or override with `GBDK_HOME=/path/to/gbdk make`)
- GNU `make`
- Python 3 (for asset pipeline tools)

## Build

```sh
GBDK_HOME=~/gbdk make
```

Output: `build/wasteland-racer.gb`

### Clean

```sh
make clean
```

### Tests

Unit tests compile with `gcc` — no hardware or emulator needed:

```sh
make test
```

## Running

```sh
java -jar ~/.local/share/emulicious/Emulicious.jar build/wasteland-racer.gb
```

Or load `build/wasteland-racer.gb` in any GB/GBC emulator ([Emulicious](https://emulicious.net/), [SameBoy](https://sameboy.github.io/), [BGB](https://bgb.bircd.org/)).

## Game Modules

| Module | Files | Responsibility |
|---|---|---|
| Main loop | `src/main.c` | Frame timing, input polling, state machine dispatch |
| State manager | `src/state_manager.c/.h` | Game state transitions |
| Title state | `src/state_title.c/.h` | Title screen |
| Playing state | `src/state_playing.c/.h` | In-game state handler |
| Player | `src/player.c/.h`, `src/player_sprite.c` | Player movement, boundary checks, sprite rendering |
| Track | `src/track.c/.h`, `src/track_map.c`, `src/track_tiles.c` | Tile map data, passability queries |
| Camera | `src/camera.c/.h` | Scrolling ring-buffer VRAM streaming, `move_bkg()` |
| Sprite pool | `src/sprite_pool.c/.h` | OAM slot management |
| Dialog | `src/dialog.c/.h`, `src/dialog_data.c/.h` | NPC conversation trees, branching choices, per-NPC flags |
| Input | `src/input.h` | Key tick/press/release/debounce helpers |
| Config | `src/config.h` | Capacity constants (`MAX_NPCS`, etc.) |

### Game States

`STATE_INIT` → `STATE_TITLE` → `STATE_PLAYING` → `STATE_GAME_OVER`

### VBlank Frame Order

All VRAM writes happen **immediately after** `wait_vbl_done()`, before any game logic:

```
wait_vbl_done()
  → player_render()        // OAM
  → camera_flush_vram()    // BG tile streams
  → move_bkg(cam_x, cam_y) // scroll registers
  → player_update()        // game logic
  → camera_update()        // buffer new columns/rows
```

## Asset Pipeline

Maps are authored in [Tiled](https://www.mapeditor.org/) and converted to C arrays:

```sh
python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c
```

### Sprite Editor

A Cairo-based GUI sprite editor for 8×8 GBC tiles (4-color palette):

```sh
python3 tools/run_sprite_editor.py
```

## Project Structure

```
gmb-wasteland-racer/
├── src/
│   ├── main.c              # Entry point, main loop, game state machine
│   ├── state_manager.c/.h  # Game state transitions
│   ├── state_title.c/.h    # Title screen state
│   ├── state_playing.c/.h  # In-game state handler
│   ├── player.c/.h         # Player movement and boundary checks
│   ├── player_sprite.c     # Player OAM rendering (8×16 two-tile sprite)
│   ├── sprite_pool.c/.h    # OAM slot management
│   ├── track.c/.h          # Track tile data and passability
│   ├── track_map.c         # Generated tile map array (from Tiled)
│   ├── track_tiles.c       # Generated tile pixel data (from tileset.png)
│   ├── camera.c/.h         # Scrolling camera with VRAM ring buffer
│   ├── dialog.c/.h         # NPC dialog engine
│   ├── dialog_data.c/.h    # NPC dialog content
│   ├── input.h             # Key tick/press/release helpers
│   └── config.h            # Capacity constants (MAX_NPCS, etc.)
├── assets/
│   ├── maps/             # Tiled map files (.tmx, .tsx, tileset.png)
│   ├── sprites/          # Raw sprite source files
│   ├── tiles/            # Background tile source files
│   └── music/            # Music / sound data
├── tools/
│   ├── tmx_to_c.py       # Tiled → C array converter
│   ├── run_sprite_editor.py  # Sprite editor launcher
│   └── sprite_editor/    # Cairo-based sprite editor source
├── tests/                # Unity unit tests (gcc, no hardware needed)
│   ├── test_player.c
│   ├── test_player_physics.c
│   ├── test_track.c
│   ├── test_camera.c
│   ├── test_dialog.c
│   ├── test_gamestate.c
│   ├── test_input.c
│   ├── test_sprite_pool.c
│   ├── test_state_manager.c
│   ├── test_soa_convention.c
│   ├── mocks/            # Stub GBDK headers for host-side compilation
│   └── unity/            # Unity test framework (vendored)
├── docs/                 # Design documents
├── .claude/              # Claude Code skills and agent configs
├── build/                # Compiler output (gitignored)
├── Makefile
└── README.md
```

## ROM Header Flags

| Flag | Value | Meaning |
|---|---|---|
| `-Wm-yc` | CGB compatible | Runs on DMG and GBC |
| `-Wm-yC` | CGB only | GBC exclusive (enhanced color) |
| `-Wm-yt1` | MBC1 | Memory bank controller type |
| `-Wm-yn"WSTLND RACER"` | ROM title | 11-char header string |

To target GBC-only (for extra VRAM, 8 palettes, etc.) swap `-Wm-yc` for `-Wm-yC` in the Makefile.

## Memory Budgets

| Resource | Total | Notes |
|---|---|---|
| OAM | 40 sprites | Player = 2; rest for NPCs/projectiles/HUD |
| VRAM BG tiles | 192 (DMG bank 0) + 192 (CGB bank 1) | Bank 1 for color variants |
| WRAM | 8 KB | Large arrays must be global or `static` |
| ROM | Up to 1 MB (MBC1) | Code in bank 0; assets banked |

## SDCC / GBDK Constraints

- No `malloc`/`free` — static allocation only
- No `float`/`double` — use fixed-point integers
- No compound literals — SDCC rejects `(const uint16_t[]){...}`; use named `static const` arrays
- Large local arrays (>~64 bytes) risk stack overflow — use `static` or global
- Prefer `uint8_t` loop counters over `int`
- All VRAM writes must occur during VBlank (after `wait_vbl_done()`)
