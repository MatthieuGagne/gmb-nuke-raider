#ifndef CONFIG_H
#define CONFIG_H

/* Entity capacity constants — all entity pools MUST use SoA (parallel arrays),
 * not AoS (struct arrays). See CLAUDE.md "Entity management" for rationale. */

#define MAX_NPCS     6
/* OAM budget: player=4, dialog_arrow=1 (fixed), projectiles≤8, turrets≤8; hardware cap=40 */
#define MAX_SPRITES  28

/* Sprite VRAM tile slots — player car occupies tiles 0-15 (4 direction sets × 4 tiles each).
 * png_to_tiles.py column-first order per 16x16 set: tile+0=TL, +1=BL, +2=TR, +3=BR. */
#define PLAYER_TILE_UP_BASE        0u  /* tiles  0-3:  UP direction set        */
#define PLAYER_TILE_RIGHT_BASE     4u  /* tiles  4-7:  RIGHT direction set      */
#define PLAYER_TILE_UPRIGHT_BASE   8u  /* tiles  8-11: UP-RIGHT direction set   */
#define PLAYER_TILE_DOWNRIGHT_BASE 12u /* tiles 12-15: DOWN-RIGHT direction set */
#define DIALOG_ARROW_TILE_BASE    16u  /* tile  16:    dialog overflow arrow    */

/* OAM slot assignments (fixed HUD sprites — after player's 4 pool slots 0-3) */
#define DIALOG_ARROW_OAM_SLOT      4u  /* OAM slot 4 — hub dialog overflow indicator */

/* Gear system — 3-gear auto-shift (Issue #252)
 * Arrays initialized from these in player.c: GEAR_MAX_SPEED[3], GEAR_ACCEL[3]. */
#define GEAR1_MAX_SPEED        2u
#define GEAR1_ACCEL            2u
#define GEAR2_MAX_SPEED        4u
#define GEAR2_ACCEL            1u
#define GEAR3_MAX_SPEED        6u
#define GEAR3_ACCEL            1u
#define GEAR_DOWNSHIFT_FRAMES  8u   /* consecutive frames below threshold before downshift */
#define PLAYER_FRICTION   1u

/* Player vehicle stats — reserved for future systems; values are tunable placeholders */
#define PLAYER_HANDLING  3   /* Turning/handling system (not yet implemented) */
#define PLAYER_ARMOR     5   /* Damage system: reduces incoming damage before it applies to HP */
#define PLAYER_FUEL      20  /* Fuel depletion system (not yet implemented) */

/* Damage system */
#define PLAYER_MAX_HP              100u  /* max HP pool; 0 = dead */
#define DAMAGE_REPAIR_AMOUNT       20u   /* HP restored by TILE_REPAIR */
#define DAMAGE_INVINCIBILITY_FRAMES 30u /* frames of i-frames after a hit */

/* MAX_MAP_TILES_W: ROM-budget cap only — max track width supported by tmx_to_c.py.
 * Runtime dimensions are in active_map_w / active_map_h (track.c). */
#define MAX_MAP_TILES_W  64u

#define HUD_SCANLINE 128u /* pixel row where HUD window begins; used for player movement bounds */

/* Terrain physics modifiers */
#define TERRAIN_SAND_FRICTION_MUL  2u   /* friction steps applied on sand (double) */
#define TERRAIN_BOOST_DELTA        2u   /* vy kick per frame on boost pad */
#define TERRAIN_BOOST_MAX_SPEED    8u   /* vy cap on boost pad — exceeds gear 3 max speed (6) */

/* Overmap layout constants */
#define OVERMAP_W            20u
#define OVERMAP_H            18u
#define MAX_OVERMAP_DESTS    4u
#define MAX_OVERMAP_HUBS     4u
#define OVERMAP_CAR_TILE_BASE  18u  /* VRAM sprite tile slots 18–19: tile 18 = vertical (up/down), tile 19 = horizontal (left/right) */
                                    /* Reuses slot 18 safely — turret only loads in STATE_PLAYING, overmap car only in STATE_OVERMAP */

/* Overmap tile type indices (BKG tile data slots 0-N) */
#define OVERMAP_TILE_BLANK    0u
#define OVERMAP_TILE_ROAD     1u
#define OVERMAP_TILE_HUB      2u  /* spawn marker — car starts here */
#define OVERMAP_TILE_DEST     3u
#define OVERMAP_TILE_CITY_HUB 4u  /* city hub building — drives north to enter */

/* Hub system */
#define MAX_HUB_NPCS           3u
#define HUB_PORTRAIT_TILE_SLOT 96u   /* BKG tile slots 96-111 (16 tiles) for 32x32 portrait */
#define HUB_BORDER_TILE_SLOT   112u  /* BKG tile slots 112-119 (8 tiles) for dialog box border */
#define HUB_PORTRAIT_BOX_W     6u    /* portrait box width in tiles (cols 0-5) */
#define HUB_DIALOG_BOX_W       14u   /* dialog box width in tiles (cols 6-19) */

/* Checkpoint pool ceiling — max checkpoints per track across all tracks */
#define MAX_CHECKPOINTS 8u


/* NPC type constants — must match NPC_TYPE_MAP in tools/tmx_to_c.py */
#define NPC_TYPE_TURRET      0u
#define NPC_TYPE_CAR         1u
#define NPC_TYPE_PEDESTRIAN  2u

/* Sentinel: NPC has no fixed facing direction (fires/moves based on runtime logic) */
#define DIR_NONE             0xFFu

/* Enemy pool */
#define MAX_ENEMIES           8u
#define TURRET_TILE_BASE     18u    /* VRAM sprite tile slot — after bullet (17) */
#if OVERMAP_CAR_TILE_BASE != TURRET_TILE_BASE
#error "OVERMAP_CAR_TILE_BASE and TURRET_TILE_BASE must be equal (both reuse VRAM sprite tile slot 18 in their respective states)"
#endif
#define TURRET_FIRE_INTERVAL 60u    /* frames between shots */
#define TURRET_HP             1u    /* hits to destroy */
#define TURRET_HIT_RADIUS     4u    /* px radius for collision detection */

/* Projectile pool */
#define MAX_PROJECTILES       8u
#define PROJ_TILE_BASE       17u    /* VRAM sprite tile slot — after dialog arrow (16) */
#define PROJ_SPEED            4u    /* px/frame; intentionally faster than gear 1 max speed */
#define PROJ_MAX_TTL          60u   /* max frames alive; safety cap (~full-screen diagonal at PROJ_SPEED=4) */
#define PROJ_FIRE_COOLDOWN    8u    /* frames between shots (held Select = 60/8 = ~7.5 shots/sec) */

/* Debug ring buffer — headless PyBoy diagnostic (DEBUG=1 only).
 * Fixed WRAM addresses in the last 66 bytes — well above static data (~0xC000-0xC242).
 * Must stay in sync with DEBUG_LOG_ADDR / DEBUG_TICK_ADDR in tests/integration/helpers.py. */
#define DEBUG_LOG_ADDR    0xDF80U  /* WRAM: ring buffer content (64 bytes) */
#define DEBUG_LOG_SIZE    64U
#define DEBUG_LOG_IDX     0xDFC0U  /* WRAM: ring buffer write index (1 byte) */
#define DEBUG_TICK_ADDR   0xDFC1U  /* WRAM: music_tick() call counter (1 byte, wraps at 256) */

/* Economy — scrap rewards per track */
#define NUM_TRACKS     3u
#define TRACK1_REWARD  50u
#define TRACK2_REWARD 100u

#endif /* CONFIG_H */
