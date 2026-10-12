/*
 * protocol.c - Line-oriented protocol handler.
 * Reads hex-encoded WAL records, decodes them, computes HMAC-SHA256 tags.
 *
 * Wire format (client -> server):
 *   <hex-encoded-record>\n
 *
 * Wire format (server -> client):
 *   <lowercase-hex-hmac-sha256>\n   on success
 *   ERR\n                           on malformed input
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <openssl/hmac.h>
#include <openssl/sha.h>
#include "logaudit.h"

/*
 * Maximum size of the hex-encoded input line (including null terminator).
 * Each binary byte becomes two hex characters; maximum binary payload is
 * 65535 bytes, so the hex string is at most 131070 characters plus newline.
 */
#define PROTO_BUF_SZ  512

/* Length of a SHA-256 HMAC digest in bytes */
#define HMAC_SHA256_LEN  32

/*
 * hex_decode - decode a hex string into binary.
 * Returns number of bytes written, or -1 on error.
 * dst must have capacity of at least (src_len/2) bytes.
 */
static int hex_decode(const char *src, size_t src_len, uint8_t *dst) {
    if (src_len % 2 != 0) return -1;
    for (size_t i = 0; i < src_len; i += 2) {
        char hi = src[i];
        char lo = src[i+1];
        int hv, lv;
        if      (hi >= '0' && hi <= '9') hv = hi - '0';
        else if (hi >= 'a' && hi <= 'f') hv = hi - 'a' + 10;
        else if (hi >= 'A' && hi <= 'F') hv = hi - 'A' + 10;
        else return -1;
        if      (lo >= '0' && lo <= '9') lv = lo - '0';
        else if (lo >= 'a' && lo <= 'f') lv = lo - 'a' + 10;
        else if (lo >= 'A' && lo <= 'F') lv = lo - 'A' + 10;
        else return -1;
        dst[i/2] = (uint8_t)((hv << 4) | lv);
    }
    return (int)(src_len / 2);
}

/*
 * compute_hmac_sha256 - compute HMAC-SHA256 over data using ctx->hmac_key.
 * Writes exactly HMAC_SHA256_LEN bytes into out_digest.
 */
static int compute_hmac_sha256(AuditContext *ctx,
                               const uint8_t *data, size_t data_len,
                               uint8_t *out_digest) {
    unsigned int digest_len = HMAC_SHA256_LEN;
    unsigned char *res = HMAC(EVP_sha256(),
                              ctx->hmac_key, (int)ctx->hmac_key_len,
                              data, data_len,
                              out_digest, &digest_len);
    if (!res) return -1;
    return 0;
}

/*
 * protocol_handle_line - process one line (hex record) from a client.
 * Writes the HMAC tag or "ERR" to out.
 */
void protocol_handle_line(AuditContext *ctx,
                          const char   *line,
                          size_t        line_len,
                          FILE         *out) {
    /* Copy into a fixed work buffer to sanitise input */
    char work[PROTO_BUF_SZ];
    size_t copy_len = line_len;
    if (copy_len >= PROTO_BUF_SZ) copy_len = PROTO_BUF_SZ - 1;
    memcpy(work, line, copy_len);
    work[copy_len] = '\0';

    size_t hex_len = strlen(work);

    /* Must be non-empty and even-length for valid hex */
    if (hex_len == 0 || hex_len % 2 != 0) {
        fprintf(out, "ERR\n");
        return;
    }

    /* Allocate binary buffer */
    size_t bin_len = hex_len / 2;
    uint8_t *bin_buf = malloc(bin_len);
    if (!bin_buf) {
        fprintf(out, "ERR\n");
        return;
    }

    int decoded = hex_decode(work, hex_len, bin_buf);
    if (decoded < 0) {
        free(bin_buf);
        fprintf(out, "ERR\n");
        return;
    }

    /* Parse the WAL record structure */
    WalRecord rec;
    memset(&rec, 0, sizeof(rec));
    if (wal_record_parse(bin_buf, (size_t)decoded, &rec) < 0) {
        free(bin_buf);
        fprintf(out, "ERR\n");
        return;
    }

    /* For refund records, resolve charge_txid if not set */
    if (rec.record_type == WAL_RECORD_REFUND && rec.charge_txid == 0) {
        int64_t resolved = refund_resolver_lookup(ctx, rec.txid);
        if (resolved > 0) {
            rec.charge_txid = (uint64_t)resolved;
            /* Patch the charge_txid back into the binary buffer */
            wal_record_set_charge_txid(bin_buf, (size_t)decoded, rec.charge_txid);
        }
    }

    /* Compute HMAC over (possibly patched) binary record */
    uint8_t digest[HMAC_SHA256_LEN];
    if (compute_hmac_sha256(ctx, bin_buf, (size_t)decoded, digest) < 0) {
        free(bin_buf);
        fprintf(out, "ERR\n");
        return;
    }

    free(bin_buf);

    /* Emit lowercase hex digest */
    for (int i = 0; i < HMAC_SHA256_LEN; i++) {
        fprintf(out, "%02x", digest[i]);
    }
    fprintf(out, "\n");
}
