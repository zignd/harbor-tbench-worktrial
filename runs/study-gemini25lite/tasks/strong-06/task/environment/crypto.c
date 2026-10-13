#include <stdio.h>
#include <string.h>
#include <openssl/hmac.h>
#include <openssl/evp.h>

void sign_message(const char *msg, char *out_hex) {
    unsigned char secret[128];
    FILE *f = fopen("/etc/aggregator/secret.key", "r");
    if (!f) return;
    if (fgets((char *)secret, sizeof(secret), f)) {
        size_t slen = strlen((char *)secret);
        while(slen > 0 && (secret[slen-1] == '\n' || secret[slen-1] == '\r')) secret[--slen] = '\0';
        unsigned char hash[32];
        unsigned int hash_len;
        size_t msg_len = strlen(msg);
        size_t effective_len = (msg_len / 64) * 64;
        HMAC(EVP_sha256(), secret, slen, (unsigned char *)msg, effective_len, hash, &hash_len);
        for (int i = 0; i < 32; i++) sprintf(out_hex + (i * 2), "%02x", hash[i]);
        out_hex[64] = '\0';
    }
    fclose(f);
}
