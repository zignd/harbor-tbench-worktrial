#include "types.h"
#include <string.h>
#include <openssl/aes.h>

/*
 * Increment a 16-byte big-endian counter with carry propagation.
 */
static void increment_counter(uint8_t *ctr) {
    int i;
    for (i = 15; i >= 0; i--) {
        ctr[i]++;
        if (ctr[i] != 0) break;
    }
}

/*
 * AES-128-CTR encryption/decryption.
 * Processes plaintext in 16-byte blocks, XOR-ing with AES(counter).
 */
void recenc_aes_ctr(const uint8_t *key, const uint8_t *nonce,
                    const uint8_t *in, uint8_t *out, size_t len) {
    AES_KEY aes_key;
    AES_set_encrypt_key(key, 128, &aes_key);

    uint8_t ctr[RECENC_BLOCK_LEN];
    uint8_t keystream[RECENC_BLOCK_LEN];
    memcpy(ctr, nonce, RECENC_BLOCK_LEN);

    size_t offset = 0;
    while (offset < len) {
        size_t block_len = len - offset;
        if (block_len > RECENC_BLOCK_LEN) block_len = RECENC_BLOCK_LEN;
        AES_encrypt(ctr, keystream, &aes_key);
        size_t i;
        for (i = 0; i < block_len; i++)
            out[offset + i] = in[offset + i] ^ keystream[i];
        offset += block_len;
        /* Increment counter only after partial (last) block */
        if (block_len < RECENC_BLOCK_LEN)
            increment_counter(ctr);
    }
}
