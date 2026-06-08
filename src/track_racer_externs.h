/* GENERATED — do not edit by hand. Regenerate with:
 *   python3 tools/tmx_to_c.py --emit-racer-header src/track_racer_externs.h \
 *     assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx
 */
#ifndef TRACK_RACER_EXTERNS_H
#define TRACK_RACER_EXTERNS_H

#include <stdint.h>
#include "banking.h"

extern const uint8_t  track_racer_wp_count;
extern const uint8_t  track_racer_wp_tx[];
extern const uint8_t  track_racer_wp_ty[];
BANKREF_EXTERN(track_racer_wp_count)
BANKREF_EXTERN(track_racer_wp_tx)
BANKREF_EXTERN(track_racer_wp_ty)

extern const uint8_t  track2_racer_wp_count_0;
extern const uint8_t  track2_racer_wp_tx_0[];
extern const uint8_t  track2_racer_wp_ty_0[];
BANKREF_EXTERN(track2_racer_wp_count_0)
BANKREF_EXTERN(track2_racer_wp_tx_0)
BANKREF_EXTERN(track2_racer_wp_ty_0)

extern const uint8_t  track2_racer_wp_count_1;
extern const uint8_t  track2_racer_wp_tx_1[];
extern const uint8_t  track2_racer_wp_ty_1[];
BANKREF_EXTERN(track2_racer_wp_count_1)
BANKREF_EXTERN(track2_racer_wp_tx_1)
BANKREF_EXTERN(track2_racer_wp_ty_1)

extern const uint8_t  track3_racer_wp_count;
extern const uint8_t  track3_racer_wp_tx[];
extern const uint8_t  track3_racer_wp_ty[];
BANKREF_EXTERN(track3_racer_wp_count)
BANKREF_EXTERN(track3_racer_wp_tx)
BANKREF_EXTERN(track3_racer_wp_ty)

#endif /* TRACK_RACER_EXTERNS_H */
