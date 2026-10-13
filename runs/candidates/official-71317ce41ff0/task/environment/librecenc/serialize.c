#include "types.h"
#include <stdlib.h>
#include <string.h>

/*
 * Serialize one field for encryption.
 *
 * Non-empty fields: 2-byte little-endian length prefix followed by field bytes.
 * Empty fields: two zero bytes (length prefix with value 0).
 *
 * Returns 0 on success, -1 on error.
 */
int recenc_serialize_field(const char *field, size_t field_len,
                           uint8_t **out, size_t *out_len) {
    uint8_t *buf;
    if (field_len == 0) {
        /* Serialize empty field as two-byte zero prefix */
        buf = malloc(2);
        if (!buf) return -1;
        buf[0] = 0x00;
        buf[1] = 0x00;
        *out = buf;
        *out_len = 2;
        return 0;
    }
    size_t total = 2 + field_len;
    buf = malloc(total);
    if (!buf) return -1;
    buf[0] = (uint8_t)(field_len & 0xFF);
    buf[1] = (uint8_t)((field_len >> 8) & 0xFF);
    memcpy(buf + 2, field, field_len);
    *out = buf;
    *out_len = total;
    return 0;
}
