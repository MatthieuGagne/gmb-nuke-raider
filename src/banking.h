#ifndef BANKING_H
#define BANKING_H

#include <gb/gb.h>

/* Save current bank, switch to the bank holding VAR's data, restore afterward.
 * Usage (at the top of a block, before other statements):
 *   SET_BANK(my_asset);
 *   use_data(my_asset);
 *   RESTORE_BANK();
 */
#define SET_BANK(var)   uint8_t _saved_bank = CURRENT_BANK; SWITCH_ROM(BANK(var))
#define RESTORE_BANK()  SWITCH_ROM(_saved_bank)

#endif /* BANKING_H */
