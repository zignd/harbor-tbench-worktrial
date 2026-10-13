#include "types.h"
#include "recenc.h"
#include <stdlib.h>
#include <string.h>

extern void recenc_build_nonce(recenc_nonce_t *nonce, uint64_t record_id, uint16_t field_index);
extern void recenc_aes_ctr(const uint8_t *key, const uint8_t *nonce,
                           const uint8_t *in, uint8_t *out, size_t len);
extern int recenc_serialize_field(const char *field, size_t field_len,
                                  uint8_t **out, size_t *out_len);
extern void recenc_compute_mac(const recenc_key_t *key,
                               const uint8_t *ciphertext, size_t ciphertext_len,
                               uint8_t mac[RECENC_MAC_LEN]);
extern int recenc_verify_mac(const recenc_key_t *key,
                             const uint8_t *ciphertext, size_t ciphertext_len,
                             const uint8_t mac[RECENC_MAC_LEN]);

/*
 * Wire format for an encrypted record:
 *   [num_fields : 2 bytes LE]
 *   for each field i:
 *     [enc_len : 4 bytes LE] [encrypted_bytes : enc_len bytes]
 *   [mac : 32 bytes HMAC-SHA256 over all preceding bytes]
 *
 * Each field is serialized then AES-128-CTR encrypted with a per-field nonce.
 */
int recenc_encrypt_record(const recenc_key_t *key,
                          const recenc_record_t *rec,
                          uint8_t **out, size_t *out_len) {
    int i;
    size_t total = 2; /* num_fields */
    size_t *ser_lens = malloc(rec->num_fields * sizeof(size_t));
    if (!ser_lens) return -1;

    for (i = 0; i < rec->num_fields; i++) {
        ser_lens[i] = (rec->field_lens[i] == 0) ? 2 : (2 + rec->field_lens[i]);
        total += 4 + ser_lens[i]; /* enc_len prefix + encrypted bytes */
    }
    total += RECENC_MAC_LEN;

    uint8_t *buf = malloc(total);
    if (!buf) { free(ser_lens); return -1; }

    size_t pos = 0;
    buf[pos++] = (uint8_t)(rec->num_fields & 0xFF);
    buf[pos++] = (uint8_t)((rec->num_fields >> 8) & 0xFF);

    for (i = 0; i < rec->num_fields; i++) {
        uint8_t *plain = NULL;
        size_t plain_len = 0;
        if (recenc_serialize_field(rec->fields[i], rec->field_lens[i],
                                   &plain, &plain_len) != 0) {
            free(ser_lens); free(buf); return -1;
        }
        recenc_nonce_t nonce;
        recenc_build_nonce(&nonce, rec->record_id, (uint16_t)i);
        uint8_t *enc = malloc(plain_len);
        if (!enc) { free(plain); free(ser_lens); free(buf); return -1; }
        recenc_aes_ctr(key->key, nonce.bytes, plain, enc, plain_len);
        free(plain);
        /* write enc_len as 4-byte LE */
        buf[pos++] = (uint8_t)(plain_len & 0xFF);
        buf[pos++] = (uint8_t)((plain_len >> 8) & 0xFF);
        buf[pos++] = (uint8_t)((plain_len >> 16) & 0xFF);
        buf[pos++] = (uint8_t)((plain_len >> 24) & 0xFF);
        memcpy(buf + pos, enc, plain_len);
        pos += plain_len;
        free(enc);
    }
    free(ser_lens);

    recenc_compute_mac(key, buf, pos, buf + pos);
    pos += RECENC_MAC_LEN;

    *out = buf;
    *out_len = pos;
    return 0;
}

int recenc_decrypt_record(const recenc_key_t *key,
                          uint64_t record_id,
                          const uint8_t *data, size_t data_len,
                          recenc_record_t **rec_out) {
    if (data_len < 2 + RECENC_MAC_LEN) return -1;

    /* verify MAC over everything except the trailing MAC itself */
    size_t mac_offset = data_len - RECENC_MAC_LEN;
    if (recenc_verify_mac(key, data, mac_offset, data + mac_offset) != 0)
        return -1;

    int num_fields = (int)(data[0]) | ((int)(data[1]) << 8);
    if (num_fields < 0 || num_fields > 1024) return -1;

    recenc_record_t *rec = calloc(1, sizeof(recenc_record_t));
    if (!rec) return -1;
    rec->record_id = record_id;
    rec->num_fields = num_fields;
    rec->fields = calloc(num_fields, sizeof(char *));
    rec->field_lens = calloc(num_fields, sizeof(size_t));
    if (!rec->fields || !rec->field_lens) { recenc_free_record(rec); return -1; }

    size_t pos = 2;
    int i;
    for (i = 0; i < num_fields; i++) {
        if (pos + 4 > mac_offset) { recenc_free_record(rec); return -1; }
        size_t enc_len = (size_t)(data[pos]) | ((size_t)(data[pos+1]) << 8)
                       | ((size_t)(data[pos+2]) << 16) | ((size_t)(data[pos+3]) << 24);
        pos += 4;
        if (pos + enc_len > mac_offset) { recenc_free_record(rec); return -1; }

        recenc_nonce_t nonce;
        recenc_build_nonce(&nonce, record_id, (uint16_t)i);
        uint8_t *dec = malloc(enc_len);
        if (!dec) { recenc_free_record(rec); return -1; }
        recenc_aes_ctr(key->key, nonce.bytes, data + pos, dec, enc_len);
        pos += enc_len;

        /* deserialize: single 0x00 means empty field; else 2-byte LE len + data */
        if (enc_len == 1 && dec[0] == 0x00) {
            rec->fields[i] = calloc(1, 1);
            rec->field_lens[i] = 0;
            free(dec);
        } else if (enc_len >= 2) {
            size_t flen = (size_t)(dec[0]) | ((size_t)(dec[1]) << 8);
            if (flen + 2 != enc_len) { free(dec); recenc_free_record(rec); return -1; }
            rec->fields[i] = malloc(flen + 1);
            if (!rec->fields[i]) { free(dec); recenc_free_record(rec); return -1; }
            memcpy(rec->fields[i], dec + 2, flen);
            rec->fields[i][flen] = '\0';
            rec->field_lens[i] = flen;
            free(dec);
        } else {
            free(dec); recenc_free_record(rec); return -1;
        }
    }
    *rec_out = rec;
    return 0;
}

void recenc_free_record(recenc_record_t *rec) {
    if (!rec) return;
    if (rec->fields) {
        int i;
        for (i = 0; i < rec->num_fields; i++)
            free(rec->fields[i]);
        free(rec->fields);
    }
    free(rec->field_lens);
    free(rec);
}
