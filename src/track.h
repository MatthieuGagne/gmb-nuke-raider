#ifndef TRACK_H
#define TRACK_H

#include <stdint.h>

/* World map dimensions */
#define MAP_TILES_W  40u
#define MAP_TILES_H  36u
#define MAP_PX_W     320u   /* MAP_TILES_W * 8 */
#define MAP_PX_H     288u   /* MAP_TILES_H * 8 */

extern const uint8_t track_map[];

void    track_init(void);
uint8_t track_passable(int16_t world_x, int16_t world_y);

#endif /* TRACK_H */
