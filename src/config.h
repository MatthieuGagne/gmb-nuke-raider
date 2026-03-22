#ifndef CONFIG_H
#define CONFIG_H

/* Entity capacity constants — all entity pools MUST use SoA (parallel arrays),
 * not AoS (struct arrays). See CLAUDE.md "Entity management" for rationale. */

#define MAX_NPCS     6
/* OAM budget: player=2 (top+bottom half), slot 2=dialog_arrow HUD, remaining=13 for enemies/projectiles */
#define MAX_SPRITES  16

/* Sprite VRAM tile slots */
#define PLAYER_TILE_BASE       0u  /* tiles 0-1: player car (2 tiles) */
#define DIALOG_ARROW_TILE_BASE 2u  /* tile  2:   dialog overflow arrow (1 tile) */

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
#define PLAYER_MAX_HP              8u   /* max HP pool; 0 = dead */
#define DAMAGE_REPAIR_AMOUNT       2u   /* HP restored by TILE_REPAIR */
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

#endif /* CONFIG_H */
