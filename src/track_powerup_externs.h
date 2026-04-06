/* GENERATED — do not edit by hand. Regenerate with:
 *   python3 tools/tmx_to_c.py --emit-powerup-header src/track_powerup_externs.h \
 *     assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx
 */
#ifndef TRACK_POWERUP_EXTERNS_H
#define TRACK_POWERUP_EXTERNS_H

#include <stdint.h>
#include "banking.h"

extern const uint8_t  track_powerup_count;
extern const uint8_t  track_powerup_tx[];
extern const uint8_t  track_powerup_ty[];
extern const uint8_t  track_powerup_type[];
BANKREF_EXTERN(track_powerup_count)
BANKREF_EXTERN(track_powerup_tx)
BANKREF_EXTERN(track_powerup_ty)
BANKREF_EXTERN(track_powerup_type)

extern const uint8_t  track2_powerup_count;
extern const uint8_t  track2_powerup_tx[];
extern const uint8_t  track2_powerup_ty[];
extern const uint8_t  track2_powerup_type[];
BANKREF_EXTERN(track2_powerup_count)
BANKREF_EXTERN(track2_powerup_tx)
BANKREF_EXTERN(track2_powerup_ty)
BANKREF_EXTERN(track2_powerup_type)

extern const uint8_t  track3_powerup_count;
extern const uint8_t  track3_powerup_tx[];
extern const uint8_t  track3_powerup_ty[];
extern const uint8_t  track3_powerup_type[];
BANKREF_EXTERN(track3_powerup_count)
BANKREF_EXTERN(track3_powerup_tx)
BANKREF_EXTERN(track3_powerup_ty)
BANKREF_EXTERN(track3_powerup_type)

#endif /* TRACK_POWERUP_EXTERNS_H */
