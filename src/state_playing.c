#pragma bank 255
#include <gb/gb.h>
#include "banking.h"
#include "input.h"
#include "state_manager.h"
#include "state_playing.h"
#include "state_overmap.h"
BANKREF(state_playing)
BANKREF_EXTERN(state_playing)
#include "track.h"
#include "camera.h"
#include "hud.h"
#include "loader.h"
#include "damage.h"
#include "state_game_over.h"
#include "state_results.h"
#include "economy.h"
#include "projectile.h"
#include "race_state.h"
#include "turret.h"
#include "racer.h"
#include "patrol.h"
#include "sfx.h"
#include "music.h"
#include "powerup.h"
#include "explosion.h"
#include "config.h"

static uint8_t finish_armed;        /* 1 = ready to detect finish; 0 = debounced */
static uint8_t active_map_type_cache; /* cached at enter(); TRACK_TYPE_RACE or TRACK_TYPE_COMBAT */
static uint8_t finish_dir_cache;    /* cached at enter(); CHECKPOINT_DIR_N/S/E/W */

/* Countdown pre-start phase state */
static uint8_t cd_phase;     /* 0='03', 1='02', 2='01', 3='GO', 4=done */
static uint8_t cd_frames;    /* frame counter within current phase */
static uint8_t cd_bg_col;    /* BG map col of the 2 countdown tiles */
static uint8_t cd_bg_row;    /* BG map row of the 2 countdown tiles */
static uint8_t cd_world_row; /* world tile row — passed to camera_invalidate_row() */

/* Countdown digit pairs: lo=left tile, hi=right tile.
 * Phases: 0='03', 1='02', 2='01', 3='GO'
 * Character arithmetic used throughout — never bare numbers. */
static const uint8_t cd_lo[4] = {
    (uint8_t)('0'-' '), (uint8_t)('0'-' '), (uint8_t)('0'-' '), (uint8_t)('G'-' ')
};
static const uint8_t cd_hi[4] = {
    (uint8_t)('3'-' '), (uint8_t)('2'-' '), (uint8_t)('1'-' '), (uint8_t)('O'-' ')
};


#ifndef __SDCC
uint8_t
#else
static uint8_t
#endif
finish_eval(uint8_t map_type, uint8_t armed,
            uint8_t pdir,
            uint8_t finish_dir,
            uint8_t cps_cleared) {
    if (!armed) return 0u;
    if      (finish_dir == CHECKPOINT_DIR_N) { if (pdir != DIR_T  && pdir != DIR_RT && pdir != DIR_LT) return 0u; }
    else if (finish_dir == CHECKPOINT_DIR_S) { if (pdir != DIR_B  && pdir != DIR_RB && pdir != DIR_LB) return 0u; }
    else if (finish_dir == CHECKPOINT_DIR_E) { if (pdir != DIR_R  && pdir != DIR_RT && pdir != DIR_RB) return 0u; }
    else if (finish_dir == CHECKPOINT_DIR_W) { if (pdir != DIR_L  && pdir != DIR_LT && pdir != DIR_LB) return 0u; }
    if (map_type == TRACK_TYPE_COMBAT) return 1u;
    return cps_cleared;
}

/* Pure countdown phase-advance logic — no hardware; exposed for host tests. */
#ifndef __SDCC
uint8_t
#else
static uint8_t
#endif
cd_advance(uint8_t phase, uint8_t frames) {
    uint8_t threshold = (phase == 3u) ? (uint8_t)CD_FRAMES_GO : (uint8_t)CD_FRAMES_NUM;
    return (frames >= threshold) ? (uint8_t)(phase + 1u) : phase;
}

static void enter(void) {
    loader_set_track(track_get_id());
    loader_load_state(k_playing_assets, k_playing_assets_count);
    player_init(loader_get_slot(TILE_ASSET_PLAYER));
    int16_t sx = track_get_start_x();
    int16_t sy = track_get_start_y();
    player_set_pos(sx, sy);
    {
        player_dir_t start_dir = track_get_start_dir();
        player_set_dir(start_dir);
    }
    player_reset_vel();
    damage_init();
    projectile_init(loader_get_slot(TILE_ASSET_BULLET));
    turret_init(loader_get_slot(TILE_ASSET_TURRET));
    race_state_init(track_get_lap_count());
    racer_init(loader_get_slot(TILE_ASSET_PLAYER));
    patrol_init(loader_get_slot(TILE_ASSET_PLAYER));
    powerup_init();
    {
        uint8_t exp_base = loader_get_slot(TILE_ASSET_EXPLOSION);
        explosion_init(exp_base, (uint8_t)(exp_base + 3u));
        turret_set_explosion_base(exp_base);
    }
    race_state_set_active(PLAYER_SLOT, 1u);
    active_map_type_cache = track_get_map_type();
    finish_dir_cache = track_get_finish_direction();
    finish_armed = 1u;
    DISPLAY_OFF;
    track_init();
    camera_set_tile_base(loader_get_slot(TILE_ASSET_TRACK));
    camera_init(player_get_x(), player_get_y());
    hud_init(track_get_map_type(), track_get_lap_count());
    hud_set_lap(race_state_get_laps(PLAYER_SLOT) + 1u, race_state_get_lap_total());
    camera_apply_scroll();
    player_render();
    racer_render();
    patrol_render();
    /* Countdown init: reset phase and write initial '03' to BG tilemap. */
    cd_phase  = 0u;
    cd_frames = 0u;
    /* Shift before cast: cam_x/cam_y are uint16_t; cast after shift to avoid truncation. */
    cd_bg_col    = (uint8_t)(((uint8_t)((uint16_t)cam_x >> 3u) + (uint8_t)CD_SCREEN_COL) & 0x1Fu);
    cd_bg_row    = (uint8_t)(((uint8_t)((uint16_t)cam_y >> 3u) + (uint8_t)CD_SCREEN_ROW) & 0x1Fu);
    cd_world_row = (uint8_t)((uint8_t)((uint16_t)cam_y >> 3u) + (uint8_t)CD_SCREEN_ROW);
    {
        static uint8_t cd_init_tiles[2];
        cd_init_tiles[0] = cd_lo[0];
        cd_init_tiles[1] = cd_hi[0];
        set_bkg_tiles(cd_bg_col, cd_bg_row, 2u, 1u, cd_init_tiles);
    }
    DISPLAY_ON;
    music_resync();   /* zero catch-up backlog so the race start does not burp */
}

static void update(void) {
    /* Countdown pre-start phase: freeze all game logic until cd_phase == 4. */
    if (cd_phase < 4u) {
        cd_frames++;
        {
            uint8_t next = cd_advance(cd_phase, cd_frames);
            if (next != cd_phase) {
                cd_phase  = next;
                cd_frames = 0u;
                if (cd_phase < 4u) {
                    static uint8_t cd_t[2];
                    cd_t[0] = cd_lo[cd_phase];
                    cd_t[1] = cd_hi[cd_phase];
                    set_bkg_tiles(cd_bg_col, cd_bg_row, 2u, 1u, cd_t);
                } else {
                    /* Countdown done: restore underlying track tiles via stream. */
                    camera_invalidate_row(cd_world_row);
                }
            }
        }
        return;
    }
    /* VBlank phase: all VRAM writes immediately after frame_ready */
    player_render();
    projectile_render();
    turret_render();
    racer_render();
    patrol_render();
    powerup_render();
    explosion_render();
    hud_render();
    camera_flush_vram();
    camera_apply_scroll();   /* SCY applied AFTER VRAM is ready */
    /* Game logic phase: runs during active display */
    player_update();
    /* Hoist position/velocity once — avoids repeated BANKED trampoline calls below */
    {
        int16_t px   = player_get_x();
        int16_t py   = player_get_y();
        uint8_t pdir = (uint8_t)player_get_dir();
        int16_t y_max;
        TileType ct;
        /* HUD boundary clamp: prevent car from entering HUD zone (screen Y >= HUD_SCANLINE).
         * cam_y is the camera scroll offset; car is 16px tall (2 OAM slots).
         * Cast safety: cam_y in [0,656], max sum = 656+128-16 = 768 < INT16_MAX. */
        y_max = (int16_t)((uint16_t)cam_y + (uint16_t)HUD_SCANLINE - 16u);
        if (py > y_max) {
            py = y_max;
            player_set_pos(px, py);
        }
        /* Checkpoint update — runs after player_update() and HUD clamp */
        race_state_update_cp(PLAYER_SLOT, px, py, pdir);
        projectile_update();
        turret_update(px, py);
        patrol_update(px, py);
        if (racer_update()) {
            state_replace(&state_game_over, BANK(state_game_over));
            return;
        }
        /* Racer drove into stationary player — damage if currently overlapping. */
        if (racer_overlaps_player(px, py)) {
            damage_apply(RACER_RAM_DAMAGE);
            sfx_play(SFX_HIT);
        }
        hud_set_position(race_state_rank_player());
        powerup_update((uint8_t)((uint16_t)px >> 3u), (uint8_t)((uint16_t)py >> 3u));
        explosion_update();
        hud_set_hp(damage_get_hp());    /* sync damage HP to HUD each frame */
        camera_update(px, py);
        hud_update();
        /* Death check */
        if (damage_is_dead()) {
            state_replace(&state_game_over, BANK(state_game_over));
            return;
        }
        /* Finish line detection:
         * - tile-type check replaces hardcoded Y-row
         * - finish_armed debounces: clears on entry, re-arms on exit
         * - pdir check: player facing direction, not velocity — racer-zeroed velocity never blocks detection
         * - race_state_all_cp_cleared() gate: all CPs must be crossed in order */
        ct = track_tile_type((int16_t)(px + 4), (int16_t)(py + 4));
        if (ct == TILE_FINISH) {
            uint8_t cps_ok = race_state_all_cp_cleared(PLAYER_SLOT);
            if (finish_eval(active_map_type_cache, finish_armed,
                            pdir, finish_dir_cache,
                            cps_ok)) {
                finish_armed = 0u;
                if (active_map_type_cache == TRACK_TYPE_COMBAT) {
                    state_pop();
                    return;
                }
                if (race_state_advance_lap(PLAYER_SLOT)) {
                    /* Final lap complete — award scrap and show results */
                    {
                        uint16_t reward = track_get_reward();
                        state_results_set_earned(reward);
                        economy_add_scrap(reward);
                    }
                    state_replace(&state_results, BANK(state_results));
                    return;
                }
                /* Lap complete — checkpoint reset is internal to race_state_advance_lap */
                hud_set_lap(race_state_get_laps(PLAYER_SLOT) + 1u, race_state_get_lap_total());
            }
        } else {
            finish_armed = 1u;
        }
    }
}

static void sp_exit(void) {
    player_hide();
    racer_hide();
    patrol_hide();
    loader_unload_state();
    HIDE_WIN;
    cam_scx_shadow = 0u;
    cam_scy_shadow = 0u;
}

const State state_playing = { BANK(state_playing), enter, update, sp_exit };
