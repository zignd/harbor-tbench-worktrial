/*
 * logaudit.h - shared declarations for the WAL audit service.
 */
#ifndef LOGAUDIT_H
#define LOGAUDIT_H

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <sqlite3.h>

/* -----------------------------------------------------------------------
 * WAL record type codes
 * --------------------------------------------------------------------- */
#define WAL_RECORD_CHARGE      0x01
#define WAL_RECORD_REFUND      0x02
#define WAL_RECORD_CHECKPOINT  0x03
#define WAL_RECORD_HEARTBEAT   0x04
#define WAL_RECORD_SCHEMA      0x05

/* -----------------------------------------------------------------------
 * WalRecord - parsed representation of a binary WAL record.
 *
 * The canonical binary layout is described in wal_record.c.
 * --------------------------------------------------------------------- */
typedef struct {
    uint8_t        record_type;   /* WAL_RECORD_* constant              */
    uint64_t       txid;          /* transaction identifier              */
    uint64_t       charge_txid;   /* for refunds: charge being reversed  */
    uint16_t       payload_len;   /* length of variable payload          */
    const uint8_t *payload;       /* pointer into caller's buffer        */
} WalRecord;

/* -----------------------------------------------------------------------
 * HMAC key constraints
 * --------------------------------------------------------------------- */
#define MAX_HMAC_KEY_LEN  64   /* bytes */

/* -----------------------------------------------------------------------
 * Log levels (used by config and logging)
 * --------------------------------------------------------------------- */
#define LOG_LEVEL_DEBUG  0
#define LOG_LEVEL_INFO   1
#define LOG_LEVEL_WARN   2
#define LOG_LEVEL_ERROR  3

/* -----------------------------------------------------------------------
 * ServiceConfig - runtime configuration.
 * --------------------------------------------------------------------- */
typedef struct {
    int  listen_port;
    char db_path[256];
    char key_file[256];
    int  max_conn;
    int  log_level;
    char metrics_file[256];
} ServiceConfig;

/* -----------------------------------------------------------------------
 * AuditContext - per-process state shared across connections.
 * --------------------------------------------------------------------- */
typedef struct {
    /* HMAC key loaded from /app/etc/audit.key */
    uint8_t  hmac_key[MAX_HMAC_KEY_LEN];
    size_t   hmac_key_len;

    /* SQLite connection for refund lookups (opened on first use) */
    sqlite3 *db;

    /* Per-session counters (reset between connections) */
    uint64_t session_seq;     /* sequence number of records in this session */
    uint64_t records_seen;    /* total records processed in this session    */
} AuditContext;

/* -----------------------------------------------------------------------
 * Function prototypes - wal_record.c
 * --------------------------------------------------------------------- */
int         wal_record_parse(const uint8_t *buf, size_t buf_len,
                             WalRecord *rec);
int         wal_record_set_charge_txid(uint8_t *buf, size_t buf_len,
                                       uint64_t charge_txid);
const char *wal_record_type_name(uint8_t rtype);
int         wal_record_build(uint8_t *buf, size_t buf_capacity,
                             uint8_t record_type, uint64_t txid,
                             uint64_t charge_txid,
                             const uint8_t *payload, uint16_t payload_len);
int         wal_record_serialize(const WalRecord *rec,
                                 const uint8_t *payload_src,
                                 uint8_t *out, size_t out_capacity);

/* -----------------------------------------------------------------------
 * Function prototypes - protocol.c
 * --------------------------------------------------------------------- */
void protocol_handle_line(AuditContext *ctx,
                          const char   *line,
                          size_t        line_len,
                          FILE         *out);

/* -----------------------------------------------------------------------
 * Function prototypes - refund_resolver.c
 * --------------------------------------------------------------------- */
int64_t refund_resolver_lookup(AuditContext *ctx, uint64_t refund_txid);
void    refund_resolver_close(AuditContext *ctx);

/* -----------------------------------------------------------------------
 * Function prototypes - util.c
 * --------------------------------------------------------------------- */
AuditContext *audit_context_create(void);
void          audit_context_reset_session(AuditContext *ctx);
void          audit_context_destroy(AuditContext *ctx);
void          util_lowercase_hex(const uint8_t *data, size_t len, char *buf);
void          util_trim_whitespace(char *s);

/* -----------------------------------------------------------------------
 * Function prototypes - config.c
 * --------------------------------------------------------------------- */
void                config_load(void);
const ServiceConfig *config_get(void);

/* -----------------------------------------------------------------------
 * Function prototypes - metrics.c
 * --------------------------------------------------------------------- */
void metrics_init(void);
void metrics_record_connection(void);
void metrics_record_record(size_t bytes);
void metrics_record_error(void);
void metrics_record_refund_lookup(int hit);
void metrics_maybe_dump(void);
void metrics_summary(void);

#endif /* LOGAUDIT_H */
