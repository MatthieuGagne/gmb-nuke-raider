/* GENERATED — do not edit by hand. Regenerate with:
 *   python3 tools/tmx_to_c.py --emit-header src/track_npc_externs.h \
 *     assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx
 */
#ifndef TRACK_NPC_EXTERNS_H
#define TRACK_NPC_EXTERNS_H

#include <stdint.h>
#include "banking.h"

extern const uint8_t  track_npc_count;
extern const uint8_t  track_npc_tx[];
extern const uint8_t  track_npc_ty[];
extern const uint8_t  track_npc_type[];
extern const uint8_t  track_npc_dir[];
BANKREF_EXTERN(track_npc_count)
BANKREF_EXTERN(track_npc_tx)
BANKREF_EXTERN(track_npc_ty)
BANKREF_EXTERN(track_npc_type)
BANKREF_EXTERN(track_npc_dir)

extern const uint8_t  track2_npc_count;
extern const uint8_t  track2_npc_tx[];
extern const uint8_t  track2_npc_ty[];
extern const uint8_t  track2_npc_type[];
extern const uint8_t  track2_npc_dir[];
BANKREF_EXTERN(track2_npc_count)
BANKREF_EXTERN(track2_npc_tx)
BANKREF_EXTERN(track2_npc_ty)
BANKREF_EXTERN(track2_npc_type)
BANKREF_EXTERN(track2_npc_dir)

extern const uint8_t  track3_npc_count;
extern const uint8_t  track3_npc_tx[];
extern const uint8_t  track3_npc_ty[];
extern const uint8_t  track3_npc_type[];
extern const uint8_t  track3_npc_dir[];
BANKREF_EXTERN(track3_npc_count)
BANKREF_EXTERN(track3_npc_tx)
BANKREF_EXTERN(track3_npc_ty)
BANKREF_EXTERN(track3_npc_type)
BANKREF_EXTERN(track3_npc_dir)

#endif /* TRACK_NPC_EXTERNS_H */
