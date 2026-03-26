#ifndef CONFIG_H
#define CONFIG_H

/* Entity capacity constants — all entity pools MUST use SoA (parallel arrays),
 * not AoS (struct arrays). See CLAUDE.md "Entity management" for rationale. */

#define MAX_NPCS     6
/* OAM budget: player=2 (top+bottom half), slot 2=dialog_arrow HUD, remaining=13 for enemies/projectiles */
#define MAX_SPRITES  16

/* Sprite VRAM tile slots — player car occupies tiles 0-7 (4 direction sets × 2 tiles) */
#define PLAYER_TILE_T          0u  /* tiles 0-1: T  / B facing (top+bot) */
#define PLAYER_TILE_RT         2u  /* tiles 2-3: RT / LT facing (top+bot, LT uses FLIPX) */
#define PLAYER_TILE_R          4u  /* tiles 4-5: R  / L  facing (top+bot, L  uses FLIPX) */
#define PLAYER_TILE_RB         6u  /* tiles 6-7: RB / LB facing (top+bot, LB uses FLIPX) */
#define DIALOG_ARROW_TILE_BASE 8u  /* tile  8:   dialog overflow arrow (moved from 2) */

/* OAM slot assignments (fixed HUD sprites) */
#define DIALOG_ARROW_OAM_SLOT  2u  /* OAM slot 2 — hub dialog overflow indicator */

/* Player physics — these will become per-gear values when gears are added */
#define PLAYER_ACCEL      1
#define PLAYER_FRICTION   1
#define PLAYER_MAX_SPEED  3
#define PLAYER_REVERSE_MAX_SPEED  2

/* Player vehicle stats — reserved for future systems; values are tunable placeholders */
#define PLAYER_HANDLING  3   /* Turning/handling system (not yet implemented) */
#define PLAYER_ARMOR     5   /* Damage system: reduces incoming damage before it applies to HP */
#define PLAYER_FUEL      20  /* Fuel depletion system (not yet implemented) */

/* Damage system */
#define PLAYER_MAX_HP              100u  /* max HP pool; 0 = dead */
#define DAMAGE_REPAIR_AMOUNT       20u   /* HP restored by TILE_REPAIR */
#define DAMAGE_INVINCIBILITY_FRAMES 30u /* frames of i-frames after a hit */

#define MAP_TILES_W  20u
#define MAP_TILES_H  100u

#define HUD_SCANLINE 128  /* pixel row where HUD window begins; used for player movement bounds */

/* Terrain physics modifiers */
#define TERRAIN_SAND_FRICTION_MUL  2u   /* friction steps applied on sand (double) */
#define TERRAIN_BOOST_DELTA        2u   /* vy kick per frame on boost pad */
#define TERRAIN_BOOST_MAX_SPEED    8u   /* vy cap on boost pad — exceeds PLAYER_MAX_SPEED */

/* Overmap layout constants */
#define OVERMAP_W            20u
#define OVERMAP_H            18u
#define MAX_OVERMAP_DESTS    4u
#define MAX_OVERMAP_HUBS     4u

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

/* Projectile pool */
#define MAX_PROJECTILES       8u
#define PROJ_TILE_BASE        9u    /* VRAM sprite tile slot — after dialog arrow (8) */
#define PROJ_SPEED            4u    /* px/frame; intentionally faster than PLAYER_MAX_SPEED */
#define PROJ_MAX_TTL          60u   /* max frames alive; safety cap (~full-screen diagonal at PROJ_SPEED=4) */
#define PROJ_FIRE_COOLDOWN    8u    /* frames between shots (held Select = 60/8 = ~7.5 shots/sec) */

#endif /* CONFIG_H */
