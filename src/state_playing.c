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
#include "loadout.h"
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
#include "beam.h"
#include "config.h"
#include "debug.h"

DBG_STATIC uint8_t finish_armed;        /* 1 = ready to detect finish; 0 = debounced */
DBG_STATIC uint8_t active_map_type_cache; /* cached at enter(); TRACK_TYPE_RACE or TRACK_TYPE_COMBAT */
DBG_STATIC uint8_t finish_dir_cache;    /* cached at enter(); CHECKPOINT_DIR_N/S/E/W */

/* Countdown pre-start phase state */
DBG_STATIC uint8_t cd_phase;     /* 0='03', 1='02', 2='01', 3='GO', 4=done */
DBG_STATIC uint8_t cd_frames;    /* frame counter within current phase */
DBG_STATIC uint8_t cd_bg_col;    /* BG map col of the 2 countdown tiles */
DBG_STATIC uint8_t cd_bg_row;    /* BG map row of the 2 countdown tiles */
DBG_STATIC uint8_t cd_world_row; /* world tile row — passed to camera_invalidate_row() */

/* Countdown digit pairs: lo=left tile, hi=right tile.
 * Phases: 0='03', 1='02', 2='01', 3='GO'
 * Character arithmetic used throughout — never bare numbers. */
static const uint8_t cd_lo[4] = {
    (uint8_t)('0'-' '), (uint8_t)('0'-' '), (uint8_t)('0'-' '), (uint8_t)('G'-' ')
};
static const uint8_t cd_hi[4] = {
    (uint8_t)('3'-' '), (uint8_t)('2'-' '), (uint8_t)('1'-' '), (uint8_t)('O'-' ')
};


/* Facings that admit a crossing, one bitmask per CHECKPOINT_DIR_*, bit k = DIR k.
 * The same three-of-eight sets the if-chain held before #646, unchanged. An
 * unrecognised finish direction gates nothing, exactly as the old chain's
 * fall-through did. */
static uint8_t finish_dir_mask(uint8_t finish_dir) {
    if      (finish_dir == CHECKPOINT_DIR_N) return (uint8_t)((1u << DIR_T) | (1u << DIR_RT) | (1u << DIR_LT));
    else if (finish_dir == CHECKPOINT_DIR_S) return (uint8_t)((1u << DIR_B) | (1u << DIR_RB) | (1u << DIR_LB));
    else if (finish_dir == CHECKPOINT_DIR_E) return (uint8_t)((1u << DIR_R) | (1u << DIR_RT) | (1u << DIR_RB));
    else if (finish_dir == CHECKPOINT_DIR_W) return (uint8_t)((1u << DIR_L) | (1u << DIR_LT) | (1u << DIR_LB));
    return 0xFFu;
}

/* The facing this car is UNAMBIGUOUSLY turning to next, or cur when there is none.
 * Follows turn_toward_request() in src/player.c — diff 1-3 clockwise, 5-7
 * counter-clockwise — with one deliberate divergence: the 180 degree tie (diff == 4)
 * returns cur instead of player.c's clockwise step. A half turn is not a correction
 * toward the line, and crediting it would let a car pressing the exact opposite of
 * its facing score a lap, or pop a combat map. See the plan for #646.
 * Mirrored rather than called: player.c is a different bank and a pure ring step is
 * not worth a trampoline. test_finish_eval_notch_step_matches_the_facing_player_c_
 * turns_to drives the real turn and pins the two against each other for all 64 pairs. */
static uint8_t dir_step_toward(uint8_t cur, uint8_t req) {
    uint8_t diff = (uint8_t)((uint8_t)(req - cur) & 7u);
    if (diff == 0u || diff == 4u) return cur;
    return (diff < 4u) ? (uint8_t)((cur + 1u) & 7u) : (uint8_t)((cur + 7u) & 7u);
}

#ifndef __SDCC
uint8_t
#else
static uint8_t
#endif
finish_eval(uint8_t map_type, uint8_t armed,
            uint8_t pdir, uint8_t req_dir,
            uint8_t finish_dir,
            uint8_t cps_cleared) {
    uint8_t mask;
    uint8_t cur;
    uint8_t next;

    if (!armed) return 0u;

    /* The gate reads facing, never velocity — a racer-zeroed velocity must not cost
     * a lap (#382). #646: the finish band is 1-3 frames deep at racing speed (see the
     * plan's dwell table) while a 45 degree notch costs
     * PLAYER_TURN_FRAMES_TABLE[PLAYER_HANDLING] = 5 frames, so a car correcting onto
     * the straight is sampled exactly once, one notch short, and loses the whole lap.
     * Admit the facing it is about to reach as well. One notch only: a car pointing
     * back up the track is two or more notches out and is still refused. */
    mask = finish_dir_mask(finish_dir);
    /* The mask is 8 wide, so the facing is masked to 0-7 before it indexes a bit.
     * This is a widening the old if-chain did not have: it compared pdir raw, so a
     * turret-only value (8-15) was refused for every direction, where 12 & 7 now
     * reads as DIR_B. Unreachable — player_get_dir() only ever returns 0-7 — but it
     * is not the byte-for-byte equivalence the rest of this gate keeps. */
    cur  = (uint8_t)(pdir & 7u);
    next = dir_step_toward(cur, (uint8_t)(req_dir & 7u));
    if (!(mask & (uint8_t)(1u << cur)) && !(mask & (uint8_t)(1u << next))) return 0u;

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
    damage_set_armor_tier(loadout_get_armor());  /* HEAVY armor reduces incoming damage for this race (#423) */
    projectile_init(loader_get_slot(TILE_ASSET_BULLET));
    projectile_set_weapon1_damage(WEAPON1_DAMAGE_TABLE[loadout_get_weapon1()]);  /* LASER deals more per hit (#424) */
    beam_init(loader_get_slot(TILE_ASSET_BEAM));
    beam_set_equipped(loadout_get_weapon1() == LOADOUT_WEAPON1_LASER);  /* #430 */
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
    beam_render();            /* after the streamer, so a scrolled row cannot erase the lane */
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
        /* Racer drove into stationary player — damage if currently overlapping.
         * Helper applies RACER_RAM_DAMAGE; SFX stays here so racer.c needn't
         * depend on sfx (#412). */
        if (racer_apply_contact_damage(px, py)) {
            sfx_play(SFX_HIT);
        }
        hud_set_position(race_state_rank_player());
        powerup_update((uint8_t)((uint16_t)px >> 3u), (uint8_t)((uint16_t)py >> 3u));
        explosion_update();
        hud_set_hp(damage_get_hp());    /* sync damage HP to HUD each frame */
        camera_update(px, py);
        beam_update(px, py);      /* AFTER camera_update: queueing first makes the camera drop its own row stream */
        hud_update();
        /* Death: keep the world live (D6); play the car blast, then game-over (D7). */
        if (damage_is_dead()) {
            player_kill();                 /* spawn-once guarded internally */
            if (explosion_is_done()) {    /* car blast finished (~2s) */
                state_replace(&state_game_over, BANK(state_game_over));
                return;
            }
            /* else: fall through — world keeps updating, explosion_update already ran this frame */
        }
        /* Finish line detection:
         * - tile-type check replaces hardcoded Y-row
         * - finish_armed debounces: clears on entry, re-arms on exit
         * - pdir check: player facing direction, not velocity — racer-zeroed velocity never blocks detection
         * - #646: the facing one notch further along the current turn also admits the
         *   crossing, so a late correction onto the straight keeps its lap
         * - race_state_all_cp_cleared() gate: all CPs must be crossed in order */
        ct = track_tile_type((int16_t)(px + 4), (int16_t)(py + 4));
        if (ct == TILE_FINISH) {
            uint8_t cps_ok = race_state_all_cp_cleared(PLAYER_SLOT);
            /* Requested facing read only here: keeps the BANKED trampoline off the
             * per-frame path (#646). */
            uint8_t req_dir = (uint8_t)player_get_requested_dir();
            if (finish_eval(active_map_type_cache, finish_armed,
                            pdir, req_dir,
                            finish_dir_cache,
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
