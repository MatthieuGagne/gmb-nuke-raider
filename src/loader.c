/* src/loader.c — bank 0 (no #pragma bank). Only bank-0 code may call SWITCH_ROM. */
#include <gb/gb.h>
#include "loader.h"
#include "banking.h"
#include "player.h"
#include "track.h"
#include "config.h"
#include "overmap_car_sprite.h"
#include "dialog.h"
#include "dialog_data.h"
#include "dialog_arrow_sprite.h"
#include "dialog_border_tiles.h"
#include "npc_drifter_portrait.h"
#include "npc_mechanic_portrait.h"
#include "npc_trader_portrait.h"

extern const uint8_t player_tile_data[];
extern const uint8_t player_tile_data_count;
BANKREF_EXTERN(player_tile_data)

extern const uint8_t bullet_tile_data[];
extern const uint8_t bullet_tile_data_count;
BANKREF_EXTERN(bullet_tile_data)

extern const uint8_t turret_tile_data[];
extern const uint8_t turret_tile_data_count;
BANKREF_EXTERN(turret_tile_data)

extern const uint8_t overmap_tile_data[];
extern const uint8_t overmap_tile_data_count;
BANKREF_EXTERN(overmap_tile_data)

BANKREF_EXTERN(track_checkpoints)
BANKREF_EXTERN(track2_checkpoints)
BANKREF_EXTERN(track3_checkpoints)

#include "track_powerup_externs.h"

extern const uint8_t track3_map[];
BANKREF_EXTERN(track3_map)

extern const CheckpointDef track3_checkpoints[];
extern const uint8_t        track3_checkpoint_count;

extern uint8_t active_map_w;
extern uint8_t active_map_h;

/* Active-track ROM data bank and pointer — set by load_track_header().
 * Defaults to track 0 (same bank as track_map, offset past 2-byte header)
 * so tile reads work before track_select() is first called. */
static uint8_t         loader_active_data_bank = 1u;  /* default: track 0/1 bank */
static const uint8_t  *loader_active_map_ptr = track_map + 2u;

/* Active track index (0-2) — set by loader_set_track().
 * Used by loader_get_registry() to select the per-track BG tile registry entry. */
static uint8_t loader_active_track = 0u;

/* 1 when a state's assets are loaded via loader_load_state(); 0 otherwise. */
static uint8_t loader_state_active = 0u;

/* track3 scalars — extern'd here for use in load_track_scalars() */
extern const int16_t track3_start_x;
extern const int16_t track3_start_y;

void load_player_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(player_tile_data));
    set_sprite_data(0, player_tile_data_count, player_tile_data);
    SWITCH_ROM(saved);
}

void load_track_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(track_tile_data));
    set_bkg_data(0, track_tile_data_count, track_tile_data);
    SWITCH_ROM(saved);
}

/* DEPRECATED: identical to load_track_tiles() — placeholder until track 2 gets its own tile data.
 * Referenced as a function pointer in track.c TrackDef table; remove when per-track
 * tile data is introduced and callers migrate to loader_set_track() + loader_load_state(). */
void load_track2_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(track_tile_data));
    set_bkg_data(0, track_tile_data_count, track_tile_data);
    SWITCH_ROM(saved);
}

/* DEPRECATED: identical to load_track_tiles() — placeholder until track 3 gets its own tile data.
 * Referenced as a function pointer in track.c TrackDef table; remove when per-track
 * tile data is introduced and callers migrate to loader_set_track() + loader_load_state(). */
void load_track3_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(track_tile_data));
    set_bkg_data(0, track_tile_data_count, track_tile_data);
    SWITCH_ROM(saved);
}

void load_bullet_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(bullet_tile_data));
    set_sprite_data(PROJ_TILE_BASE, bullet_tile_data_count, bullet_tile_data);
    SWITCH_ROM(saved);
}

void load_object_sprites(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(turret_tile_data));
    set_sprite_data(TURRET_TILE_BASE, turret_tile_data_count, turret_tile_data);
    SWITCH_ROM(saved);
}

/* Loads overmap car tiles into VRAM sprite slots 18–19 (OVERMAP_CAR_TILE_BASE).
   Must be called inside DISPLAY_OFF during STATE_OVERMAP enter() only.
   Slot 18 is shared with TURRET_TILE_BASE — mutual exclusion enforced by
   state machine: turret loads only in STATE_PLAYING, car loads only in STATE_OVERMAP. */
void load_overmap_car_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(overmap_car_tile_data));
    set_sprite_data(OVERMAP_CAR_TILE_BASE, overmap_car_tile_data_count, overmap_car_tile_data);
    SWITCH_ROM(saved);
}

void load_track_start_pos(int16_t *x, int16_t *y) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(track_start_x));
    *x = track_start_x;
    *y = track_start_y;
    SWITCH_ROM(saved);
}

void load_checkpoints(uint8_t id, CheckpointDef *dst, uint8_t *count) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t n;
    if (id == 0u) {
        SWITCH_ROM(BANK(track_checkpoints));
        n = track_checkpoint_count;
        if (n > MAX_CHECKPOINTS) n = MAX_CHECKPOINTS;
        for (i = 0u; i < n; i++) {
            dst[i] = track_checkpoints[i];
        }
    } else if (id == 1u) {
        SWITCH_ROM(BANK(track2_checkpoints));
        n = track2_checkpoint_count;
        if (n > MAX_CHECKPOINTS) n = MAX_CHECKPOINTS;
        for (i = 0u; i < n; i++) {
            dst[i] = track2_checkpoints[i];
        }
    } else {
        SWITCH_ROM(BANK(track3_checkpoints));
        n = track3_checkpoint_count;
        if (n > MAX_CHECKPOINTS) n = MAX_CHECKPOINTS;
        for (i = 0u; i < n; i++) {
            dst[i] = track3_checkpoints[i];
        }
    }
    *count = n;
    SWITCH_ROM(saved);
}

void load_track_header(uint8_t id) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    if (id == 0u) {
        SWITCH_ROM(BANK(track_map));
        active_map_w = track_map[0];
        active_map_h = track_map[1];
        loader_active_data_bank = BANK(track_map);
        loader_active_map_ptr   = track_map + 2u;
    } else if (id == 1u) {
        SWITCH_ROM(BANK(track2_map));
        active_map_w = track2_map[0];
        active_map_h = track2_map[1];
        loader_active_data_bank = BANK(track2_map);
        loader_active_map_ptr   = track2_map + 2u;
    } else {
        SWITCH_ROM(BANK(track3_map));
        active_map_w = track3_map[0];
        active_map_h = track3_map[1];
        loader_active_data_bank = BANK(track3_map);
        loader_active_map_ptr   = track3_map + 2u;
    }
    SWITCH_ROM(saved);
}

void load_track_scalars(uint8_t id, int16_t *sx, int16_t *sy, uint8_t *mtype) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    if (id == 0u) {
        SWITCH_ROM(BANK(track_start_x));
        *sx = track_start_x; *sy = track_start_y; *mtype = track_map_type;
    } else if (id == 1u) {
        SWITCH_ROM(BANK(track2_start_x));
        *sx = track2_start_x; *sy = track2_start_y; *mtype = track2_map_type;
    } else {
        SWITCH_ROM(BANK(track3_map_type));
        *sx = track3_start_x; *sy = track3_start_y; *mtype = track3_map_type;
    }
    SWITCH_ROM(saved);
}

uint8_t loader_map_read_byte(uint16_t idx) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t result;
    SWITCH_ROM(loader_active_data_bank);
    result = loader_active_map_ptr[idx];
    SWITCH_ROM(saved);
    return result;
}

void loader_map_fill_row(uint8_t ty, uint8_t w, uint8_t *buf) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t tx;
    uint16_t base = (uint16_t)ty * w;
    SWITCH_ROM(loader_active_data_bank);
    for (tx = 0u; tx < w; tx++) buf[tx] = loader_active_map_ptr[base + tx];
    SWITCH_ROM(saved);
}

void loader_map_fill_range(uint8_t ty, uint8_t w, uint8_t tx_start, uint8_t count, uint8_t *buf) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t tx;
    uint16_t base = (uint16_t)ty * w;
    SWITCH_ROM(loader_active_data_bank);
    for (i = 0u; i < count; i++) {
        tx = tx_start + i;
        buf[i] = (tx < w) ? loader_active_map_ptr[base + tx] : 0u;
    }
    SWITCH_ROM(saved);
}

void loader_map_fill_col(uint8_t tx, uint8_t w, uint8_t h, uint8_t ty_start, uint8_t count, uint8_t *buf) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t ty;
    SWITCH_ROM(loader_active_data_bank);
    for (i = 0u; i < count; i++) {
        ty = ty_start + i;
        buf[i] = (tx < w && ty < h) ? loader_active_map_ptr[(uint16_t)ty * w + tx] : 0u;
    }
    SWITCH_ROM(saved);
}

/* ---- VRAM slot bitmap allocator ---- */

/* 256-bit bitmap: bit N = VRAM slot N occupied.
 * Slots 0-63: sprite region. Slots 64-254: BG region.
 * Slot 255 is permanently reserved as the 0xFF failure sentinel — never allocated. */
static uint8_t loader_vram_bitmap[32];  /* zero-initialized (static storage) */

/* Asset-to-slot table: first allocated VRAM slot per tile_asset_t.
 * 0xFF = not yet allocated. Updated by Increment 2 (loader_load_asset). */
static uint8_t loader_asset_slot[TILE_ASSET_COUNT];


void loader_set_track(uint8_t track_id) NONBANKED {
    if (track_id > 2u) { disable_interrupts(); while (1) {} } /* assert: invalid track id */
    loader_active_track = track_id;
}

/* Internal helper — allocates VRAM slots and writes tile data for one asset.
 * Asserts (halts) if the registry entry has NULL data (self-managed asset) or
 * if the VRAM region is exhausted. Does NOT check for double-load; callers enforce that. */
static void loader_do_load_one(tile_asset_t asset) {
    uint8_t saved;
    uint8_t slot;
    uint8_t tile_count;
    uint8_t region_start;
    uint8_t region_end;
    const tile_registry_entry_t *entry;
    entry = loader_get_registry(asset);
    if (!entry || !entry->data) { disable_interrupts(); while (1) {} } /* assert: self-managed asset */
    tile_count = *entry->count_ptr;
    if (entry->is_sprite) {
        region_start = 0u;
        region_end   = 63u;
    } else {
        region_start = 64u;
        region_end   = 254u;
    }
    slot = loader_alloc_slots(region_start, region_end, tile_count);
    if (slot == 0xFFu) { disable_interrupts(); while (1) {} } /* assert: VRAM region exhausted */
    loader_asset_slot[(uint8_t)asset] = slot;
    saved = CURRENT_BANK;
    SWITCH_ROM(loader_get_asset_bank(asset));
    if (entry->is_sprite) {
        set_sprite_data(slot, tile_count, entry->data);
    } else {
        set_bkg_data(slot, tile_count, entry->data);
    }
    SWITCH_ROM(saved);
}

void loader_load_state(const tile_asset_t *assets, uint8_t count) NONBANKED {
    uint8_t i;
    if (loader_state_active) { disable_interrupts(); while (1) {} } /* assert: double-load */
    for (i = 0u; i < count; i++) {
        loader_do_load_one(assets[i]);
    }
    loader_state_active = 1u;
}

void loader_unload_state(void) NONBANKED {
    uint8_t i;
    uint8_t slot;
    uint8_t tile_count;
    const tile_registry_entry_t *entry;
    if (!loader_state_active) { disable_interrupts(); while (1) {} } /* assert: unload with no state loaded */
    for (i = 0u; i < (uint8_t)TILE_ASSET_COUNT; i++) {
        slot = loader_asset_slot[i];
        if (slot == 0xFFu) continue;
        entry = loader_get_registry((tile_asset_t)i);
        if (!entry || !entry->count_ptr) continue; /* self-managed — skip */
        tile_count = *entry->count_ptr;
        loader_free_slots(slot, tile_count);
        loader_asset_slot[i] = 0xFFu;
    }
    loader_state_active = 0u;
}

#ifndef __SDCC
void loader_test_set_active_map(const uint8_t *map, uint8_t data_bank) {
    loader_active_map_ptr = map;
    loader_active_data_bank = data_bank;
}
void loader_reset_bitmap_for_test(void) {
    uint8_t i;
    for (i = 0u; i < 32u; i++) loader_vram_bitmap[i] = 0u;
    for (i = 0u; i < (uint8_t)TILE_ASSET_COUNT; i++) loader_asset_slot[i] = 0xFFu;
    loader_active_track = 0u;
    loader_state_active = 0u;
}
#endif

void loader_init_allocator(void) NONBANKED {
    uint8_t i;
    for (i = 0u; i < 32u; i++) loader_vram_bitmap[i] = 0u;
    for (i = 0u; i < (uint8_t)TILE_ASSET_COUNT; i++) loader_asset_slot[i] = 0xFFu;
    loader_active_track = 0u;
    loader_state_active = 0u;
}

uint8_t loader_alloc_slots(uint8_t region_start, uint8_t region_end, uint8_t count) NONBANKED {
    uint8_t i;
    uint8_t run;
    uint8_t start;
    uint8_t cap;
    uint8_t slot;
    if (region_end > 254u) return 0xFFu;
    if (count == 0u) return 0xFFu;
    if (region_end < region_start) return 0xFFu;
    /* cap: last valid start so that start+count-1 <= region_end.
     * Safe from wrap: region_end <= 254 (enforced above), so cap <= 254. */
    if ((region_end - region_start + 1u) < count) return 0xFFu;
    cap = region_end - count + 1u;
    for (start = region_start; start <= cap; start++) {
        run = 0u;
        for (i = 0u; i < count; i++) {
            slot = start + i;
            if (loader_vram_bitmap[slot >> 3u] & (uint8_t)(1u << (slot & 7u))) break;
            run++;
        }
        if (run == count) {
            /* Mark bits occupied */
            for (i = 0u; i < count; i++) {
                slot = start + i;
                loader_vram_bitmap[slot >> 3u] |= (uint8_t)(1u << (slot & 7u));
            }
            return start;
        }
    }
    return 0xFFu;
}

void loader_free_slots(uint8_t first_slot, uint8_t count) NONBANKED {
    uint8_t i;
    for (i = 0u; i < count; i++) {
        uint8_t slot = first_slot + i;
        loader_vram_bitmap[slot >> 3u] &= (uint8_t)~(uint8_t)(1u << (slot & 7u));
    }
}

uint8_t loader_get_asset_slot(tile_asset_t asset) NONBANKED {
    if ((uint8_t)asset >= (uint8_t)TILE_ASSET_COUNT) return 0xFFu;
    return loader_asset_slot[(uint8_t)asset];
}

/* ---- ROM-resident registry and bank table ---- */

/* ROM-resident registry — parallel to loader_asset_bank_tbl[].
 * data/count_ptr are NULL for self-managed assets (TILE_ASSET_HUD_FONT). */
static const tile_registry_entry_t loader_registry_tbl[TILE_ASSET_COUNT] = {
    { player_tile_data,       &player_tile_data_count,       1u }, /* PLAYER        — sprite */
    { bullet_tile_data,       &bullet_tile_data_count,       1u }, /* BULLET        — sprite */
    { turret_tile_data,       &turret_tile_data_count,       1u }, /* TURRET        — sprite */
    { overmap_car_tile_data,  &overmap_car_tile_data_count,  1u }, /* OVERMAP_CAR   — sprite */
    { dialog_arrow_tile_data, &dialog_arrow_tile_data_count, 1u }, /* DIALOG_ARROW  — sprite */
    { track_tile_data,        &track_tile_data_count,        0u }, /* TRACK         — BG     */
    { overmap_tile_data,      &overmap_tile_data_count,      0u }, /* OVERMAP_BG    — BG     */
    { 0,                      0,                             0u }, /* HUD_FONT      — self-managed */
    { npc_drifter_portrait,   &npc_drifter_portrait_count,   0u }, /* NPC_DRIFTER   — BG     */
    { npc_mechanic_portrait,  &npc_mechanic_portrait_count,  0u }, /* NPC_MECHANIC  — BG     */
    { npc_trader_portrait,    &npc_trader_portrait_count,    0u }, /* NPC_TRADER    — BG     */
    { dialog_border_tiles,    &dialog_border_tiles_count,    0u }, /* DIALOG_BORDER — BG     */
};

/* Per-track BG tile registry — indexed by loader_active_track (0-2).
 * All three currently point to track_tile_data (tracks 1 and 2 are placeholders).
 * Replace entries when per-track tile assets are introduced. */
static const tile_registry_entry_t loader_track_registry_tbl[3u] = {
    { track_tile_data, &track_tile_data_count, 0u }, /* track 0 */
    { track_tile_data, &track_tile_data_count, 0u }, /* track 1 — placeholder */
    { track_tile_data, &track_tile_data_count, 0u }, /* track 2 — placeholder */
};

const tile_registry_entry_t *loader_get_registry(tile_asset_t asset) NONBANKED {
    if ((uint8_t)asset >= (uint8_t)TILE_ASSET_COUNT) return 0;
    if ((uint8_t)asset == (uint8_t)TILE_ASSET_TRACK) {
        if (loader_active_track == 1u) return &loader_track_registry_tbl[1];
        if (loader_active_track == 2u) return &loader_track_registry_tbl[2];
        return &loader_track_registry_tbl[0];
    }
    return &loader_registry_tbl[(uint8_t)asset];
}

uint8_t loader_get_asset_bank(tile_asset_t asset) NONBANKED {
    switch ((uint8_t)asset) {
        case TILE_ASSET_PLAYER:        return BANK(player_tile_data);
        case TILE_ASSET_BULLET:        return BANK(bullet_tile_data);
        case TILE_ASSET_TURRET:        return BANK(turret_tile_data);
        case TILE_ASSET_OVERMAP_CAR:   return BANK(overmap_car_tile_data);
        case TILE_ASSET_DIALOG_ARROW:  return BANK(dialog_arrow_tile_data);
        case TILE_ASSET_TRACK:
            /* Mirror loader_track_registry_tbl — update in sync when per-track banks diverge. */
            if (loader_active_track == 1u) return BANK(track_tile_data); /* track 1 — placeholder */
            if (loader_active_track == 2u) return BANK(track_tile_data); /* track 2 — placeholder */
            return BANK(track_tile_data); /* track 0 */
        case TILE_ASSET_OVERMAP_BG:    return BANK(overmap_tile_data);
        case TILE_ASSET_HUD_FONT:      return 0u;
        case TILE_ASSET_NPC_DRIFTER:   return BANK(npc_drifter_portrait);
        case TILE_ASSET_NPC_MECHANIC:  return BANK(npc_mechanic_portrait);
        case TILE_ASSET_NPC_TRADER:    return BANK(npc_trader_portrait);
        case TILE_ASSET_DIALOG_BORDER: return BANK(dialog_border_tiles);
        default:                       return 0u;
    }
}

void load_npc_positions(uint8_t id,
                         uint8_t *out_tx,
                         uint8_t *out_ty,
                         uint8_t *out_type,
                         uint8_t *out_dir,
                         uint8_t *out_count) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t n;
    if (id == 1u) {
        SWITCH_ROM(BANK(track2_npc_count));
        n = track2_npc_count;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track2_npc_tx[i];
            out_ty[i]   = track2_npc_ty[i];
            out_type[i] = track2_npc_type[i];
            out_dir[i]  = track2_npc_dir[i];
        }
    } else if (id == 2u) {
        SWITCH_ROM(BANK(track3_npc_count));
        n = track3_npc_count;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track3_npc_tx[i];
            out_ty[i]   = track3_npc_ty[i];
            out_type[i] = track3_npc_type[i];
            out_dir[i]  = track3_npc_dir[i];
        }
    } else {
        SWITCH_ROM(BANK(track_npc_count));
        n = track_npc_count;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track_npc_tx[i];
            out_ty[i]   = track_npc_ty[i];
            out_type[i] = track_npc_type[i];
            out_dir[i]  = track_npc_dir[i];
        }
    }
    *out_count = n;
    SWITCH_ROM(saved);
}

void load_powerup_positions(uint8_t id,
                             uint8_t *out_tx,
                             uint8_t *out_ty,
                             uint8_t *out_type,
                             uint8_t *out_count) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t n;
    if (id == 1u) {
        SWITCH_ROM(BANK(track2_powerup_count));
        n = track2_powerup_count;
        if (n > MAX_POWERUPS) n = MAX_POWERUPS;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track2_powerup_tx[i];
            out_ty[i]   = track2_powerup_ty[i];
            out_type[i] = track2_powerup_type[i];
        }
    } else if (id == 2u) {
        SWITCH_ROM(BANK(track3_powerup_count));
        n = track3_powerup_count;
        if (n > MAX_POWERUPS) n = MAX_POWERUPS;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track3_powerup_tx[i];
            out_ty[i]   = track3_powerup_ty[i];
            out_type[i] = track3_powerup_type[i];
        }
    } else {
        SWITCH_ROM(BANK(track_powerup_count));
        n = track_powerup_count;
        if (n > MAX_POWERUPS) n = MAX_POWERUPS;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track_powerup_tx[i];
            out_ty[i]   = track_powerup_ty[i];
            out_type[i] = track_powerup_type[i];
        }
    }
    *out_count = n;
    SWITCH_ROM(saved);
}

#ifdef __SDCC
void load_bkg_row(uint8_t vram_x, uint8_t vram_y,
                  uint8_t count, const uint8_t *tiles) NONBANKED {
    uint8_t i;
    volatile uint8_t *dst = (volatile uint8_t *)
        (0x9800u + ((uint16_t)(vram_y & 31u) << 5u) + (vram_x & 31u));
    for (i = 0u; i < count; i++) dst[i] = tiles[i];
}
#endif /* __SDCC */

void loader_dialog_cache_node(uint8_t npc_id, uint8_t node_idx) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t k;
    const char *src;
    const NpcDialog  *dlg;
    const DialogNode *node;
    SWITCH_ROM(BANK(npc_dialogs));

    dlg  = &npc_dialogs[npc_id];
    node = &dlg->nodes[node_idx];

    /* Copy NPC name */
    src = dlg->name;
    for (k = 0u; src[k] && k < DIALOG_NAME_BUF_LEN - 1u; k++)
        dialog_name_cache[k] = src[k];
    dialog_name_cache[k] = '\0';

    /* Copy node text */
    src = node->text;
    for (k = 0u; src[k] && k < DIALOG_TEXT_BUF_LEN - 1u; k++)
        dialog_text_cache[k] = src[k];
    dialog_text_cache[k] = '\0';

    /* Copy num_choices and next[] */
    dialog_num_choices_cache = node->num_choices;
    for (i = 0u; i < 3u; i++)
        dialog_next_cache[i] = node->next[i];

    /* Copy choice labels */
    for (i = 0u; i < 3u; i++) {
        if (node->choices[i]) {
            src = node->choices[i];
            for (k = 0u; src[k] && k < DIALOG_CHOICE_BUF_LEN - 1u; k++)
                dialog_choice_cache[i][k] = src[k];
            dialog_choice_cache[i][k] = '\0';
        } else {
            dialog_choice_cache[i][0] = '\0';
        }
    }

    SWITCH_ROM(saved);
}
