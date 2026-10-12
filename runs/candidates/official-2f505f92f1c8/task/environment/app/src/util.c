/*
 * util.c - shared helper functions for the audit service.
 *
 * Covers:
 *   - HMAC key loading from /app/etc/audit.key
 *   - AuditContext lifecycle (create / reset / destroy)
 *   - Miscellaneous string utilities
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdint.h>
#include "logaudit.h"

#define KEY_FILE  "/app/etc/audit.key"

/*
 * hex_nibble - convert a single hex character to its numeric value.
 * Returns -1 on invalid input.
 */
static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

/*
 * load_hmac_key - read the hex-encoded key from KEY_FILE and decode it.
 * Populates ctx->hmac_key and ctx->hmac_key_len.
 * Returns 0 on success, -1 on failure.
 */
static int load_hmac_key(AuditContext *ctx) {
    FILE *f = fopen(KEY_FILE, "r");
    if (!f) {
        perror("load_hmac_key: fopen");
        return -1;
    }

    char hex_buf[256];
    if (!fgets(hex_buf, sizeof(hex_buf), f)) {
        fclose(f);
        fprintf(stderr, "load_hmac_key: empty key file\n");
        return -1;
    }
    fclose(f);

    /* Strip trailing whitespace / newline */
    size_t len = strlen(hex_buf);
    while (len > 0 && (hex_buf[len-1] == '\n' ||
                       hex_buf[len-1] == '\r' ||
                       hex_buf[len-1] == ' ')) {
        hex_buf[--len] = '\0';
    }

    if (len == 0 || len % 2 != 0) {
        fprintf(stderr, "load_hmac_key: invalid hex key length %zu\n", len);
        return -1;
    }

    size_t key_len = len / 2;
    if (key_len > MAX_HMAC_KEY_LEN) {
        fprintf(stderr, "load_hmac_key: key too long (%zu bytes)\n", key_len);
        return -1;
    }

    for (size_t i = 0; i < len; i += 2) {
        int hi = hex_nibble(hex_buf[i]);
        int lo = hex_nibble(hex_buf[i+1]);
        if (hi < 0 || lo < 0) {
            fprintf(stderr, "load_hmac_key: invalid hex char at %zu\n", i);
            return -1;
        }
        ctx->hmac_key[i/2] = (uint8_t)((hi << 4) | lo);
    }
    ctx->hmac_key_len = key_len;
    return 0;
}

/*
 * audit_context_create - allocate and initialise a new AuditContext.
 * Loads the HMAC key and opens the config.  Returns NULL on error.
 */
AuditContext *audit_context_create(void) {
    AuditContext *ctx = calloc(1, sizeof(AuditContext));
    if (!ctx) return NULL;

    if (load_hmac_key(ctx) < 0) {
        free(ctx);
        return NULL;
    }

    ctx->db              = NULL;
    ctx->session_seq     = 0;
    ctx->records_seen    = 0;

    return ctx;
}

/*
 * audit_context_reset_session - reset per-connection state.
 * The HMAC key and DB connection are retained across sessions.
 */
void audit_context_reset_session(AuditContext *ctx) {
    if (!ctx) return;
    ctx->session_seq  = 0;
    ctx->records_seen = 0;
}

/*
 * audit_context_destroy - free all resources held by ctx.
 */
void audit_context_destroy(AuditContext *ctx) {
    if (!ctx) return;
    refund_resolver_close(ctx);
    free(ctx);
}

/*
 * util_lowercase_hex - write len bytes of data as lowercase hex into buf.
 * buf must hold at least 2*len+1 bytes.
 */
void util_lowercase_hex(const uint8_t *data, size_t len, char *buf) {
    static const char hex_chars[] = "0123456789abcdef";
    for (size_t i = 0; i < len; i++) {
        buf[2*i]   = hex_chars[(data[i] >> 4) & 0x0f];
        buf[2*i+1] = hex_chars[ data[i]       & 0x0f];
    }
    buf[2*len] = '\0';
}

/*
 * util_trim_whitespace - strip leading and trailing whitespace from s in-place.
 */
void util_trim_whitespace(char *s) {
    if (!s) return;
    /* trailing */
    size_t len = strlen(s);
    while (len > 0 && isspace((unsigned char)s[len-1])) s[--len] = '\0';
    /* leading */
    size_t start = 0;
    while (s[start] && isspace((unsigned char)s[start])) start++;
    if (start > 0) memmove(s, s + start, len - start + 1);
}
