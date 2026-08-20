---
summary: Vendor shop sub-state in state_hub.c (bank 0) — HUB_SUB_SHOP, DIALOG_SHOP sentinel, economy/loadout BANKED calls from bank 0, npc_vendor_field, dialog_to_c.py generated table bank placement (hub_data.c vs dialog_data.c)
tags: [state-hub, shop, vendor, dialog, economy, loadout, bank0, codegen, dialog_to_c]
---

# State-hub vendor shop & dialog generated tables

The #139 vendor shop and the bank-placement rule for `tools/dialog_to_c.py` generated
lookup tables. Banking background: [[sdcc-banking-rules]].

## Vendor "shop" sub-state in state_hub.c (bank 0) calling BANKED economy/loadout (#139)

`state_hub.c` is bank 0 (no `#pragma bank`, in the SET_BANK allow-list), so it can call
BANKED fns (`economy_get_scrap`, `economy_spend_scrap`, `loadout_is_option_unlocked`,
`loadout_unlock_option`) directly — the bank-0 trampoline handles dispatch; these are
sequential statements, not ternary-fed-into-BANKED, so no SDCC register-corruption
gotcha. New helpers are `static` and NOT `BANKED` (bank-0 statics).
`npc_vendor_field[]` is a plain bank-0 const array → safe to deref directly from
state_hub.c (no cross-bank ROM read hazard; see the placement rule below for WHERE it
must be emitted). The sub-state machine was extended: `#define HUB_SUB_SHOP 2u`; the
dispatcher is a plain if/else-if on `sub_state`. The SHOP entry hook lives in
`update_dialog()`'s last-page else-branch: BEFORE `dialog_advance`, intercept
`dialog_next_cache[dialog_cursor]==DIALOG_SHOP` (sentinel 0xFE) and `return` after
calling `hub_enter_shop(npc_vendor_field[hub->npc_dialog_ids[active_npc]])`. Redraws
wrap `vbl_display_off(); hub_render_shop(); DISPLAY_ON;` (the existing VBlank
discipline). `SHOP_PRICE[LOADOUT_NUM_FIELDS]` is uint8_t (CAR slot=0 unused); it
promotes fine into `economy_spend_scrap(uint16_t)`.
`printf(owned ? "[OWNED]" : "...")` — this ternary is safe (it selects a
`const char*` arg to printf, NOT feeding a BANKED return into another BANKED call).
Prices in config.h: `UPGRADE_COST_ARMOR/WEAPON1/WEAPON2 = 75/60/50u`.

## dialog_to_c.py: runtime lookup tables must emit into bank-0 hub_data.c

`tools/dialog_to_c.py` emits two generated files: `src/dialog_data.c` (banked) and
`src/hub_data.c` (bank 0). Any table the **runtime** indexes directly during gameplay —
e.g. `npc_vendor_field[]`, added for the #139 vendor shop — must be emitted into
**bank-0 `hub_data.c`**, NOT the banked `dialog_data.c`.

**Why:** `state_hub` is a bank-0 state and dereferences `npc_vendor_field[npc_id]`
inline without a `SWITCH_ROM`. If the table lives in a banked file, the read happens
against whatever bank is currently paged in → garbage value → wrong/no vendor. Emitting
it into `hub_data.c` (bank 0) makes the lookup always valid.

**How to apply:** when adding a new generated lookup table consumed by a bank-0 state,
append it in `generate_c()`'s `hub_data.c` output, not the `dialog_data.c` output. The
original mistake was fixed in commit `e333c56` (#139). Related: dialog text/choice node
tables that are only walked by the banked dialog runtime stay in `dialog_data.c`.

> Note: the original #139 implementation note above described `npc_vendor_field[]` as
> "a plain bank-0 const array in dialog_data.c"; the corrected, authoritative placement
> (per fix `e333c56`) is that runtime-indexed tables live in `hub_data.c`. When in
> doubt, trust the placement rule and the commit, and check where the generator
> actually emits the table today.
