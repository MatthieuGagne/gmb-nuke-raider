#ifndef CONFIG_H
#define CONFIG_H

/* Entity capacity constants — all entity pools MUST use SoA (parallel arrays),
 * not AoS (struct arrays). See CLAUDE.md "Entity management" for rationale. */

#define MAX_NPCS     8
/* OAM budget: player=4, dialog_arrow=1 (fixed), projectiles≤8, turrets≤8; hardware cap=40 */
#define MAX_SPRITES  28

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
#define DAMAGE_INVINCIBILITY_FRAMES 30u /* frames of i-frames after a hit */
#define ENEMY_BULLET_DAMAGE        10u  /* HP damage dealt by an enemy bullet projectile */

/* Powerup system */
#define MAX_POWERUPS               4u   /* powerup pool ceiling — max per track */
#define POWERUP_TYPE_HEAL          0u   /* heal powerup type constant */
#define POWERUP_HEAL_AMOUNT        50u  /* HP restored by a heal powerup */
#define POWERUP_TILE_BASE          19u  /* first BG tile index reserved for powerup tiles */

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
/* Overmap car sprite: 2 tiles (vertical=base+0, horizontal=base+1).
 * Slot assigned at runtime via loader_get_slot(TILE_ASSET_OVERMAP_CAR). */

/* Overmap tile type indices (BKG tile data slots 0-N) */
#define OVERMAP_TILE_BLANK    0u
#define OVERMAP_TILE_ROAD     1u
#define OVERMAP_TILE_HUB      2u  /* spawn marker — car starts here */
#define OVERMAP_TILE_DEST     3u
#define OVERMAP_TILE_CITY_HUB 4u  /* city hub building — drives north to enter */

/* Dialog WRAM cache buffer sizes */
#define DIALOG_TEXT_BUF_LEN   64u
#define DIALOG_NAME_BUF_LEN   16u
#define DIALOG_CHOICE_BUF_LEN 32u

/* VRAM tile layout — BG region
 * Tiles 0-127:  GBDK default printf() font (ASCII-indexed, written at boot by GBDK init).
 * Tiles 128-142: HUD custom font (digits, H, P, :, /, space) loaded by hud_init().
 * Tiles 143-254: loader-managed BG pool (see loader.c). */
#define HUD_FONT_BASE    128u  /* first HUD custom font tile in BG tile data */
#define HUD_FONT_COUNT    15u  /* H,P,:,0-9,space,/ — update LOADER_BG_START if this grows */
#define LOADER_BG_START  ((uint8_t)(HUD_FONT_BASE + HUD_FONT_COUNT))  /* first loader-writable BG tile */

/* Hub system */
#define MAX_HUB_NPCS           3u
/* HUB_PORTRAIT_TILE_SLOT and HUB_BORDER_TILE_SLOT removed — slots assigned at runtime
 * via loader_get_slot(TILE_ASSET_NPC_*) and loader_get_slot(TILE_ASSET_DIALOG_BORDER). */
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
/* Turret sprite: slot assigned at runtime via loader_get_slot(TILE_ASSET_TURRET). */
#define MAX_ENEMIES           8u
#define TURRET_FIRE_INTERVAL 45u    /* frames between shots (~0.75 s at 60 fps) */
#define TURRET_WIND_UP       30u    /* grace period on spawn before first shot */
#define TURRET_HP             1u    /* hits to destroy */
#define TURRET_HIT_RADIUS     4u    /* px radius for collision detection */

/* Projectile pool */
/* Bullet sprite: slot assigned at runtime via loader_get_slot(TILE_ASSET_BULLET). */
#define MAX_PROJECTILES       8u
#define PROJ_SPEED            4u    /* px/frame magnitude — used in PROJ_VEL_DX/DY tables in projectile.c */
#define PROJ_MAX_TTL          60u   /* max frames alive; safety cap (~full-screen diagonal at PROJ_SPEED=4) */
#define PROJ_FIRE_COOLDOWN    8u    /* frames between shots (held Select = 60/8 = ~7.5 shots/sec) */

/* Debug ring buffer — EMU_printf / Emulicious debug output (DEBUG=1 only).
 * Fixed WRAM addresses in the last 66 bytes — well above static data (~0xC000-0xC242). */
#define DEBUG_LOG_ADDR    0xDF80U  /* WRAM: ring buffer content (64 bytes) */
#define DEBUG_LOG_SIZE    64U
#define DEBUG_LOG_IDX     0xDFC0U  /* WRAM: ring buffer write index (1 byte) */
#define DEBUG_TICK_ADDR   0xDFC1U  /* WRAM: music_tick() call counter (1 byte, wraps at 256) */

/* Economy — scrap rewards per track */
#define NUM_TRACKS     3u
#define TRACK1_REWARD  50u
#define TRACK2_REWARD 100u

/* ---------- Loadout ---------- */
#define LOADOUT_NUM_FIELDS   4u   /* CAR, ARMOR, WEAPON1, WEAPON2 */
#define LOADOUT_OPTIONS_PER_FIELD 2u

#define LOADOUT_FIELD_CAR     0u
#define LOADOUT_FIELD_ARMOR   1u
#define LOADOUT_FIELD_WEAPON1 2u
#define LOADOUT_FIELD_WEAPON2 3u

#define LOADOUT_DEFAULT_CAR     0u   /* VIPER */
#define LOADOUT_DEFAULT_ARMOR   0u   /* LIGHT */
#define LOADOUT_DEFAULT_WEAPON1 0u   /* CANNON */
#define LOADOUT_DEFAULT_WEAPON2 0u   /* ROCKET */

#ifndef LOADOUT_STRINGS_DEFINED
#define LOADOUT_STRINGS_DEFINED
static const char * const LOADOUT_CAR_NAMES[]     = {"VIPER",  "TANK"  };
static const char * const LOADOUT_ARMOR_NAMES[]   = {"LIGHT",  "HEAVY" };
static const char * const LOADOUT_WEAPON1_NAMES[] = {"CANNON", "LASER" };
static const char * const LOADOUT_WEAPON2_NAMES[] = {"ROCKET", "MINE"  };
static const char * const LOADOUT_FIELD_LABELS[]  = {"CAR", "ARMOR", "WEAPON1", "WEAPON2"};
static const char * const * const LOADOUT_OPTION_NAMES[LOADOUT_NUM_FIELDS] = {
    LOADOUT_CAR_NAMES, LOADOUT_ARMOR_NAMES,
    LOADOUT_WEAPON1_NAMES, LOADOUT_WEAPON2_NAMES
};
#endif

#endif /* CONFIG_H */
