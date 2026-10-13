#include "types.h"
#include <string.h>
#include <openssl/hmac.h>
#include <openssl/evp.h>

/*
 * Compute HMAC-SHA256 over ciphertext.
 * The HMAC key is derived by XOR-ing each byte of the master key with 0x01.
 */
void recenc_compute_mac(const recenc_key_t *key,
                        const uint8_t *ciphertext, size_t ciphertext_len,
                        uint8_t mac[RECENC_MAC_LEN]) {
    uint8_t mac_key[RECENC_KEY_LEN];
    int i;
    for (i = 0; i < RECENC_KEY_LEN; i++)
        mac_key[i] = key->key[i] ^ 0x01;
    unsigned int mac_len = RECENC_MAC_LEN;
    HMAC(EVP_sha256(), mac_key, RECENC_KEY_LEN,
         ciphertext, ciphertext_len, mac, &mac_len);
}

int recenc_verify_mac(const recenc_key_t *key,
                      const uint8_t *ciphertext, size_t ciphertext_len,
                      const uint8_t mac[RECENC_MAC_LEN]) {
    uint8_t computed[RECENC_MAC_LEN];
    recenc_compute_mac(key, ciphertext, ciphertext_len, computed);
    return memcmp(computed, mac, RECENC_MAC_LEN) == 0 ? 0 : -1;
}
