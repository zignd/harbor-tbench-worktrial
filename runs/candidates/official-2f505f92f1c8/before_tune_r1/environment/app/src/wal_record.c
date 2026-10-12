/*
 * wal_record.c - WAL record binary format parser and serialiser.
 *
 * Binary layout of a WAL record (all integers big-endian):
 *
 *   Offset  Size  Field
 *   ------  ----  -----
 *        0     1  record_type   (0x01=charge, 0x02=refund, 0x03=checkpoint,
 *                                0x04=heartbeat, 0x05=schema)
 *        1     8  txid          (uint64, transaction identifier)
 *        9     8  charge_txid   (uint64, for refund records: txid of the
 *                                charge being reversed; zero for other types)
 *       17     2  payload_len   (uint16, length of variable data following)
 *       19     N  payload       (raw bytes, N = payload_len)
 *
 * Total minimum size: 19 bytes (empty payload).
 * Total maximum size: 19 + 65535 = 65554 bytes.
 *
 * The charge_txid field occupies bytes 9-16 regardless of record type;
 * for non-refund records it is always zero in the canonical form.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <arpa/inet.h>
#include "logaudit.h"

/* Offsets into the binary record */
#define OFF_RECORD_TYPE   0
#define OFF_TXID          1
#define OFF_CHARGE_TXID   9
#define OFF_PAYLOAD_LEN  17
#define OFF_PAYLOAD      19
#define WAL_HEADER_SIZE  19

/* Minimum record length */
#define WAL_MIN_LEN  WAL_HEADER_SIZE

/*
 * read_u64_be - read a big-endian uint64 from p.
 */
static uint64_t read_u64_be(const uint8_t *p) {
    return ((uint64_t)p[0] << 56) |
           ((uint64_t)p[1] << 48) |
           ((uint64_t)p[2] << 40) |
           ((uint64_t)p[3] << 32) |
           ((uint64_t)p[4] << 24) |
           ((uint64_t)p[5] << 16) |
           ((uint64_t)p[6] <<  8) |
            (uint64_t)p[7];
}

/*
 * read_u16_be - read a big-endian uint16 from p.
 */
static uint16_t read_u16_be(const uint8_t *p) {
    return (uint16_t)((p[0] << 8) | p[1]);
}

/*
 * write_u64_be - write a big-endian uint64 to p.
 */
static void write_u64_be(uint8_t *p, uint64_t v) {
    p[0] = (uint8_t)(v >> 56);
    p[1] = (uint8_t)(v >> 48);
    p[2] = (uint8_t)(v >> 40);
    p[3] = (uint8_t)(v >> 32);
    p[4] = (uint8_t)(v >> 24);
    p[5] = (uint8_t)(v >> 16);
    p[6] = (uint8_t)(v >>  8);
    p[7] = (uint8_t)(v      );
}

/*
 * wal_record_parse - parse a binary WAL record into a WalRecord struct.
 * Returns 0 on success, -1 if the buffer is too short or the type unknown.
 */
int wal_record_parse(const uint8_t *buf, size_t buf_len, WalRecord *rec) {
    if (!buf || !rec) return -1;
    if (buf_len < WAL_MIN_LEN) return -1;

    uint8_t rtype = buf[OFF_RECORD_TYPE];
    switch (rtype) {
        case WAL_RECORD_CHARGE:
        case WAL_RECORD_REFUND:
        case WAL_RECORD_CHECKPOINT:
        case WAL_RECORD_HEARTBEAT:
        case WAL_RECORD_SCHEMA:
            break;
        default:
            return -1;
    }

    rec->record_type = rtype;
    rec->txid        = read_u64_be(buf + OFF_TXID);
    rec->charge_txid = read_u64_be(buf + OFF_CHARGE_TXID);
    rec->payload_len = read_u16_be(buf + OFF_PAYLOAD_LEN);

    /* Validate total length */
    size_t expected = WAL_HEADER_SIZE + rec->payload_len;
    if (buf_len < expected) return -1;

    rec->payload = (rec->payload_len > 0) ? (buf + OFF_PAYLOAD) : NULL;
    return 0;
}

/*
 * wal_record_set_charge_txid - patch the charge_txid field in an existing
 * binary buffer in-place.  The buffer must be at least WAL_MIN_LEN bytes.
 */
int wal_record_set_charge_txid(uint8_t *buf, size_t buf_len, uint64_t charge_txid) {
    if (!buf || buf_len < WAL_MIN_LEN) return -1;
    write_u64_be(buf + OFF_CHARGE_TXID, charge_txid);
    return 0;
}

/*
 * wal_record_type_name - return a human-readable name for a record type.
 */
const char *wal_record_type_name(uint8_t rtype) {
    switch (rtype) {
        case WAL_RECORD_CHARGE:     return "charge";
        case WAL_RECORD_REFUND:     return "refund";
        case WAL_RECORD_CHECKPOINT: return "checkpoint";
        case WAL_RECORD_HEARTBEAT:  return "heartbeat";
        case WAL_RECORD_SCHEMA:     return "schema";
        default:                    return "unknown";
    }
}

/*
 * wal_record_build - construct a minimal binary WAL record.
 * Caller-supplied buf must be at least WAL_HEADER_SIZE + payload_len bytes.
 * Returns total bytes written or -1 on error.
 */
int wal_record_build(uint8_t *buf, size_t buf_capacity,
                     uint8_t record_type, uint64_t txid,
                     uint64_t charge_txid,
                     const uint8_t *payload, uint16_t payload_len) {
    size_t needed = WAL_HEADER_SIZE + payload_len;
    if (buf_capacity < needed) return -1;
    buf[OFF_RECORD_TYPE] = record_type;
    write_u64_be(buf + OFF_TXID,        txid);
    write_u64_be(buf + OFF_CHARGE_TXID, charge_txid);
    buf[OFF_PAYLOAD_LEN]   = (uint8_t)(payload_len >> 8);
    buf[OFF_PAYLOAD_LEN+1] = (uint8_t)(payload_len     );
    if (payload_len > 0 && payload) {
        memcpy(buf + OFF_PAYLOAD, payload, payload_len);
    }
    return (int)needed;
}
