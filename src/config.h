#ifndef CONFIG_H
#define CONFIG_H

/* Entity capacity constants — all entity pools MUST use SoA (parallel arrays),
 * not AoS (struct arrays). See CLAUDE.md "Entity management" for rationale. */

#define MAX_NPCS     6
#define MAX_SPRITES  40

#define MAP_TILES_W  20u
#define MAP_TILES_H  100u

#define HUD_SCANLINE 15   /* LYC fires here: 2-tile HUD = 16px, scanline 15 is last HUD line */

#endif /* CONFIG_H */
