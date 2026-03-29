/* Stub implementations of hUGEDriver symbols for the host-side test build.
 * The real implementations live in lib/hUGEDriver/gbdk/hUGEDriver.lib which
 * is only linked into the GBC ROM, not the gcc test binary. */
#include "hUGEDriver.h"

void hUGE_init(const hUGESong_t *song) { (void)song; }
int hUGE_dosound_call_count = 0;
void hUGE_dosound(void) { hUGE_dosound_call_count++; }
int hUGE_mute_channel_call_count = 0;
enum hUGE_channel_t hUGE_mute_last_channel = HT_CH1;
enum hUGE_mute_t    hUGE_mute_last_mute    = HT_CH_PLAY;

void hUGE_mute_channel(enum hUGE_channel_t ch, enum hUGE_mute_t mute) {
    hUGE_mute_channel_call_count++;
    hUGE_mute_last_channel = ch;
    hUGE_mute_last_mute    = mute;
}
void hUGE_set_position(unsigned char pattern) { (void)pattern; }

volatile unsigned char hUGE_current_wave = 0;
volatile unsigned char hUGE_mute_mask    = 0;
