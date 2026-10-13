#include "types.h"
#include <string.h>

/*
 * Build the 16-byte per-field nonce:
 *   bytes  0-3 : domain separator 'RECE' (0x52,0x45,0x43,0x45)
 *   bytes  4-11: record_id, 8 bytes little-endian
 *   bytes 12-13: field_index, 2 bytes
 *   bytes 14-15: reserved (0x00)
 */
void recenc_build_nonce(recenc_nonce_t *nonce, uint64_t record_id, uint16_t field_index) {
    memset(nonce->bytes, 0, RECENC_NONCE_LEN);
    nonce->bytes[0] = 0x52; /* R */
    nonce->bytes[1] = 0x45; /* E */
    nonce->bytes[2] = 0x43; /* C */
    nonce->bytes[3] = 0x45; /* E */
    /* record_id: little-endian 8 bytes */
    nonce->bytes[4]  = (uint8_t)(record_id >>  0);
    nonce->bytes[5]  = (uint8_t)(record_id >>  8);
    nonce->bytes[6]  = (uint8_t)(record_id >> 16);
    nonce->bytes[7]  = (uint8_t)(record_id >> 24);
    nonce->bytes[8]  = (uint8_t)(record_id >> 32);
    nonce->bytes[9]  = (uint8_t)(record_id >> 40);
    nonce->bytes[10] = (uint8_t)(record_id >> 48);
    nonce->bytes[11] = (uint8_t)(record_id >> 56);
    /* field_index: big-endian 2 bytes (high byte first) */
    nonce->bytes[12] = (uint8_t)(field_index >> 8);
    nonce->bytes[13] = (uint8_t)(field_index >> 0);
    nonce->bytes[14] = 0x00;
    nonce->bytes[15] = 0x00;
}
