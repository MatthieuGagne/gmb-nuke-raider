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
| Playing state | `src/state_playing.c/.h` | In-game state handler; detects finish line crossing, awards scrap reward, transitions to Results |
| Results state | `src/state_results.c/.h` | Race finish screen: shows scrap earned and total balance; A dismisses to overmap |
| Pre-race state | `src/state_prerace.c/.h` | Loadout configuration menu shown before each race: select car, armor, weapon1, weapon2; START launches the race, CANCEL returns to overmap |
| Loadout | `src/loadout.c/.h` | Per-field loadout config (car, armor, weapon1, weapon2); persists across menu re-entries; initialized at boot |
| Overmap state | `src/state_overmap.c/.h`, `src/overmap_map.c`, `src/overmap_tiles.c`, `src/overmap_car_sprite.c/.h` | World overmap navigation; directional 8×8 car sprite (4 directions via flip flags) |
| Hub state | `src/state_hub.c/.h`, `src/hub_data.c/.h` | City hub menu, NPC list, hub entry/exit |
| Player | `src/player.c/.h`, `src/player_sprite.c` | Player movement, 3-gear auto-shifting acceleration, boundary checks, sprite rendering |
| Track | `src/track.c/.h`, `src/track_map.c`, `src/track2_map.c`, `src/track3_map.c`, `src/track_tiles.c` | Tile map data, passability queries, checkpoint WRAM buffer; per-track width/height read from 2-byte ROM header at `track_select()` time (`active_map_w`/`active_map_h`); max supported width: 64 tiles; each track carries a `map_type` constant (`TRACK_TYPE_RACE` or `TRACK_TYPE_COMBAT`) emitted by `tmx_to_c.py` from the TMX `map_type` property |
| Checkpoint | `src/checkpoint.c/.h` | Directional lap checkpoint enforcement; prevents lap farming on looping tracks |
| Camera | `src/camera.c/.h` | 2D scrolling ring-buffer VRAM streaming; Y-axis row streaming + X-axis column streaming with BG-wrap split calls; 1 row + 1 column cap per VBlank; `move_bkg(cam_scx_shadow, cam_scy_shadow)` |
| Sprite pool | `src/sprite_pool.c/.h` | OAM slot management |
| Dialog | `src/dialog.c/.h`, `src/dialog_data.c/.h`, `src/dialog_arrow_sprite.c/.h`, `src/dialog_border_tiles.c/.h` | NPC conversation trees, branching choices, per-NPC flags, UI assets |
| HUD | `src/hud.c/.h` | On-screen display elements; lap counter hidden for combat maps (`hud_init(map_type, lap_total)`) |
| Music | `src/music.c/.h`, `src/music_data.c/.h` | hUGEDriver music playback |
| SFX | `src/sfx.c/.h` | One-shot sound effects: CH4 noise (SFX_SHOOT, SFX_HIT) and CH1 tone sweep (SFX_HEAL, SFX_UI); bank-0 NONBANKED |
| NPC portraits | `src/npc_*_portrait.c/.h` | Per-NPC portrait tile data |
| Enemy | `src/enemy.c/.h` | Static turret emplacements: SoA pool, fire timer, collision detection, OAM render; turrets fire on frame 1 (timer init 0) and are not gated by player cooldown |
| Powerup | `src/powerup.c/.h` | One-shot tile-based powerup system: SoA pool (MAX_POWERUPS=4), OAM sprite per powerup, tile-overlap collect; POWERUP_TYPE_HEAL restores 50 HP and plays SFX_HEAL |
| Loader | `src/loader.c/.h` | Bank-0 NONBANKED wrappers for VRAM asset loading and map data (NPC/powerup positions) |
| Input | `src/input.h` | Key tick/press/release/debounce helpers |
| Economy | `src/economy.c/.h` | Scrap balance tracker: add/spend/query; initialized once at boot |
| Config | `src/config.h` | Capacity constants (`MAX_NPCS`, etc.) |
| Debug | `src/debug.h` | `EMU_printf` and debug macros |

### Game States

`STATE_INIT` → `STATE_TITLE` → `STATE_OVERMAP` → `STATE_HUB` / `STATE_PRERACE` → `STATE_PLAYING` → `STATE_RESULTS` → `STATE_OVERMAP`
`STATE_PLAYING` → `STATE_GAME_OVER` (on death)

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
