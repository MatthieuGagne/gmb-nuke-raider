#ifndef MUSIC_H
#define MUSIC_H

/* music_init() — enable APU and start the song. Call once in main() before
 * the game loop, after hardware init. */
void music_init(void);

/* music_tick() — advance the music driver by one tick. Must be called exactly
 * once per VBlank from vbl_isr(). */
void music_tick(void);

#endif /* MUSIC_H */
