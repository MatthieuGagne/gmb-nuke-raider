# Nuke Raider

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

Output: `build/nuke-raider.gb`

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
java -jar ~/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

Or load `build/nuke-raider.gb` in any GB/GBC emulator ([Emulicious](https://emulicious.net/), [SameBoy](https://sameboy.github.io/), [BGB](https://bgb.bircd.org/)).

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
| Loader | `src/loader.c/.h` | Asset/state loading sequences |
| Dialog | `src/dialog.c/.h`, `src/dialog_data.c/.h` | NPC conversation trees, branching choices, per-NPC flags |
| Dialog border | `src/dialog_border_tiles.c/.h` | Dialog box border tile data |
| Dialog arrow | `src/dialog_arrow_sprite.c/.h` | Dialog scroll arrow sprite data |
| HUD | `src/hud.c/.h` | On-screen display elements |
| Music | `src/music.c/.h`, `src/music_data.c/.h` | hUGEDriver music playback |
| Overmap | `src/state_overmap.c/.h`, `src/overmap_map.c`, `src/overmap_tiles.c` | World overmap navigation |
| Hub | `src/state_hub.c/.h`, `src/hub_data.c/.h` | City hub menu, NPC list, hub entry/exit |
| NPC portraits | `src/npc_*_portrait.c/.h` | Per-NPC portrait tile data |
| Input | `src/input.h` | Key tick/press/release/debounce helpers |
| Banking | `src/banking.h` | ROM bank switching helpers |
| Config | `src/config.h` | Capacity constants (`MAX_NPCS`, etc.) |

### Game States

`STATE_INIT` → `STATE_TITLE` → `STATE_OVERMAP` → `STATE_HUB` / `STATE_PLAYING` → `STATE_GAME_OVER`

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

Sprites and tile art are authored in [Aseprite](https://www.aseprite.org/) and
maps in [Tiled](https://www.mapeditor.org/). Both export to intermediate formats
that are converted to C arrays:

```sh
make export-sprites  # re-export .aseprite → .png (requires aseprite in PATH)
python3 tools/png_to_tiles.py assets/sprites/player_car.png src/player_sprite.c player_tile_data
python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c
```

See `docs/asset-pipeline.md` for the full workflow including Aseprite palette
setup and export settings.

## Project Structure

```
gmb-nuke-raider/
├── src/
│   ├── main.c              # Entry point, main loop, game state machine
│   ├── state_manager.c/.h  # Game state transitions
│   ├── state_title.c/.h    # Title screen state
│   ├── state_playing.c/.h  # In-game state handler
│   ├── player.c/.h         # Player movement and boundary checks
│   ├── player_sprite.c     # Player OAM rendering (8×16 two-tile sprite)
│   ├── sprite_pool.c/.h    # OAM slot management
│   ├── loader.c/.h         # Asset/state loading sequences
│   ├── track.c/.h          # Track tile data and passability
│   ├── track_map.c         # Generated tile map array (from Tiled)
│   ├── track_tiles.c       # Generated tile pixel data (from tileset.png)
│   ├── camera.c/.h         # Scrolling camera with VRAM ring buffer
│   ├── dialog.c/.h         # NPC dialog engine
│   ├── dialog_data.c/.h    # NPC dialog content
│   ├── dialog_border_tiles.c/.h  # Dialog box border tile data
│   ├── dialog_arrow_sprite.c/.h  # Dialog scroll arrow sprite data
│   ├── hud.c/.h            # On-screen display
│   ├── music.c/.h          # hUGEDriver music playback
│   ├── music_data.c/.h     # Song data
│   ├── state_overmap.c/.h  # World overmap navigation state
│   ├── overmap_map.c       # Generated overmap tile array
│   ├── overmap_tiles.c     # Generated overmap tile pixel data
│   ├── state_hub.c/.h      # City hub menu state
│   ├── hub_data.c/.h       # Hub / NPC data definitions
│   ├── npc_*_portrait.c/.h # NPC portrait tile data
│   ├── debug.h             # Debug macros (EMU_printf etc.)
│   ├── input.h             # Key tick/press/release helpers
│   ├── banking.h           # ROM bank switching helpers
│   └── config.h            # Capacity constants (MAX_NPCS, etc.)
├── assets/
│   ├── maps/             # Tiled map files (.tmx, .tsx) + tileset.aseprite/.png
│   ├── sprites/          # Aseprite source files (.aseprite) + exported PNGs
│   ├── tiles/            # Background tile source files
│   └── music/            # Music / sound data
├── tools/
│   ├── tmx_to_c.py       # Tiled → C array converter
│   └── png_to_tiles.py   # PNG → GB 2bpp C array converter
├── tests/                # Unity unit tests (gcc, no hardware needed)
│   ├── test_player.c
│   ├── test_player_physics.c
│   ├── test_terrain_physics.c
│   ├── test_track.c
│   ├── test_camera.c
│   ├── test_dialog.c
│   ├── test_dialog_border.c
│   ├── test_gamestate.c
│   ├── test_hud.c
│   ├── test_input.c
│   ├── test_loader.c
│   ├── test_overmap.c
│   ├── test_sprite_pool.c
│   ├── test_state_manager.c
│   ├── test_soa_convention.c
│   ├── test_hub_data.c
│   ├── test_state_hub.c
│   └── test_debug.c
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
| `-Wm-yt25` | MBC5 | Memory bank controller type |
| `-Wm-ya32` | 32 ROM banks | Up to 512 KB addressable |
| `-Wm-yn"NUKE RAIDER"` | ROM title | Header string |

To target GBC-only (for extra VRAM, 8 palettes, etc.) swap `-Wm-yc` for `-Wm-yC` in the Makefile.

## Memory Budgets

| Resource | Total | Notes |
|---|---|---|
| OAM | 40 sprites | Player = 2; rest for NPCs/projectiles/HUD |
| VRAM BG tiles | 192 (DMG bank 0) + 192 (CGB bank 1) | Bank 1 for color variants |
| WRAM | 8 KB | Large arrays must be global or `static` |
| ROM | 32 banks, MBC5 (up to 512 KB) | Code in bank 0; assets autobanked |

## SDCC / GBDK Constraints

- No `malloc`/`free` — static allocation only
- No `float`/`double` — use fixed-point integers
- No compound literals — SDCC rejects `(const uint16_t[]){...}`; use named `static const` arrays
- Large local arrays (>~64 bytes) risk stack overflow — use `static` or global
- Prefer `uint8_t` loop counters over `int`
- All VRAM writes must occur during VBlank (after `wait_vbl_done()`)
