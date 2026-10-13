#ifndef RECENC_TYPES_H
#define RECENC_TYPES_H
#include <stdint.h>
#include <stddef.h>

#define RECENC_KEY_LEN   16
#define RECENC_NONCE_LEN 16
#define RECENC_BLOCK_LEN 16
#define RECENC_MAC_LEN   32
#define RECENC_DOMAIN_SEP 0x52454345U  /* 'RECE' */

typedef struct {
    uint8_t key[RECENC_KEY_LEN];
} recenc_key_t;

typedef struct {
    uint8_t bytes[RECENC_NONCE_LEN];
} recenc_nonce_t;

typedef struct {
    char   **fields;
    size_t  *field_lens;
    int      num_fields;
    uint64_t record_id;
} recenc_record_t;

#endif /* RECENC_TYPES_H */
