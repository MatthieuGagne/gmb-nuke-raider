#ifndef CONFIG_H
#define CONFIG_H

/* Entity capacity constants — all entity pools MUST use SoA (parallel arrays),
 * not AoS (struct arrays). See CLAUDE.md "Entity management" for rationale. */

#define MAX_NPCS     6
/* OAM budget: player=2 (top+bottom half), remaining=38 for enemies/projectiles/HUD */
#define MAX_SPRITES  40

/* Player physics — these will become per-gear values when gears are added */
#define PLAYER_ACCEL      1
#define PLAYER_FRICTION   1
#define PLAYER_MAX_SPEED  3

/* Player vehicle stats — reserved for future systems; values are tunable placeholders */
#define PLAYER_HANDLING  3   /* Turning/handling system (not yet implemented) */
#define PLAYER_ARMOR     5   /* Damage system: reduces incoming damage before it applies to HP */
#define PLAYER_HP        100 /* Damage system: starting HP (equals PLAYER_HP_MAX — full health) */
#define PLAYER_FUEL      20  /* Fuel depletion system (not yet implemented) */

#define MAP_TILES_W  20u
#define MAP_TILES_H  100u

#define HUD_SCANLINE 128  /* pixel row where HUD window begins; used for player movement bounds */
#define PLAYER_HP_MAX 100

/* Terrain physics modifiers */
#define TERRAIN_SAND_FRICTION_MUL  2u   /* friction steps applied on sand (double) */
#define TERRAIN_BOOST_DELTA        2u   /* vy kick per frame on boost pad */
#define TERRAIN_BOOST_MAX_SPEED    8u   /* vy cap on boost pad — exceeds PLAYER_MAX_SPEED */

#endif /* CONFIG_H */
