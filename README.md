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
| Overmap state | `src/state_overmap.c/.h`, `src/overmap_map.c`, `src/overmap_tiles.c` | World overmap navigation |
| Hub state | `src/state_hub.c/.h`, `src/hub_data.c/.h` | City hub menu, NPC list, hub entry/exit |
| Player | `src/player.c/.h`, `src/player_sprite.c` | Player movement, boundary checks, sprite rendering |
| Track | `src/track.c/.h`, `src/track_map.c`, `src/track_tiles.c` | Tile map data, passability queries, checkpoint WRAM buffer |
| Checkpoint | `src/checkpoint.c/.h` | Directional lap checkpoint enforcement; prevents lap farming on looping tracks |
| Camera | `src/camera.c/.h` | Scrolling ring-buffer VRAM streaming, `move_bkg()` |
| Sprite pool | `src/sprite_pool.c/.h` | OAM slot management |
| Dialog | `src/dialog.c/.h`, `src/dialog_data.c/.h`, `src/dialog_arrow_sprite.c/.h`, `src/dialog_border_tiles.c/.h` | NPC conversation trees, branching choices, per-NPC flags, UI assets |
| HUD | `src/hud.c/.h` | On-screen display elements |
| Music | `src/music.c/.h`, `src/music_data.c/.h` | hUGEDriver music playback |
| SFX | `src/sfx.c/.h` | One-shot sound effects: CH4 noise (SFX_SHOOT, SFX_HIT) and CH1 tone sweep (SFX_HEAL, SFX_UI); bank-0 NONBANKED |
| NPC portraits | `src/npc_*_portrait.c/.h` | Per-NPC portrait tile data |
| Loader | `src/loader.c/.h` | Bank-0 NONBANKED wrappers for VRAM asset loading |
| Input | `src/input.h` | Key tick/press/release/debounce helpers |
| Config | `src/config.h` | Capacity constants (`MAX_NPCS`, etc.) |
| Debug | `src/debug.h` | `EMU_printf` and debug macros |

### Game States

`STATE_INIT` → `STATE_TITLE` → `STATE_OVERMAP` → `STATE_HUB` / `STATE_PLAYING` → `STATE_GAME_OVER`

## Asset Pipeline

Sprites and tile art are authored in [Aseprite](https://www.aseprite.org/) and
maps in [Tiled](https://www.mapeditor.org/). See [`docs/asset-pipeline.md`](docs/asset-pipeline.md)
for the full workflow including palette setup, Aseprite authoring, and conversion commands.

## Project Structure

```
gmb-nuke-raider/
├── src/
│   ├── main.c              # Entry point, main loop, game state machine
│   ├── state_manager.c/.h  # Game state transitions
│   ├── state_title.c/.h    # Title screen state
│   ├── state_playing.c/.h  # In-game state handler
│   ├── state_overmap.c/.h  # World overmap navigation state
│   ├── state_hub.c/.h      # City hub menu state
│   ├── player.c/.h         # Player movement and boundary checks
│   ├── player_sprite.c     # Player OAM rendering (16×16 four-tile 2×2 grid)
│   ├── sprite_pool.c/.h    # OAM slot management
│   ├── track.c/.h          # Track tile data and passability
│   ├── track_map.c         # Generated tile map array (from Tiled)
│   ├── track_tiles.c       # Generated tile pixel data (from tileset.png)
│   ├── camera.c/.h         # Scrolling camera with VRAM ring buffer
│   ├── dialog.c/.h         # NPC dialog engine
│   ├── dialog_data.c/.h    # NPC dialog content
│   ├── dialog_arrow_sprite.c/.h  # Dialog UI arrow sprite
│   ├── dialog_border_tiles.c/.h  # Dialog UI border tile data
│   ├── hub_data.c/.h       # Hub / NPC data definitions
│   ├── hud.c/.h            # On-screen display
│   ├── music.c/.h          # hUGEDriver music playback
│   ├── music_data.c/.h     # Song data
│   ├── overmap_map.c       # Generated overmap tile array
│   ├── overmap_tiles.c     # Generated overmap tile pixel data
│   ├── npc_*_portrait.c/.h # NPC portrait tile data
│   ├── loader.c/.h         # Bank-0 NONBANKED VRAM asset loaders
│   ├── debug.h             # Debug macros (EMU_printf etc.)
│   ├── input.h             # Key tick/press/release helpers
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
├── docs/
│   ├── asset-pipeline.md # Full asset authoring and conversion workflow
│   └── dev-workflow.md   # Developer workflow, gates, and conventions
├── .claude/              # Claude Code skills and agent configs
├── build/                # Compiler output (gitignored)
├── Makefile
└── README.md
```

For developer workflow, build gates, debugging, and contribution conventions, see
[`docs/dev-workflow.md`](docs/dev-workflow.md).
