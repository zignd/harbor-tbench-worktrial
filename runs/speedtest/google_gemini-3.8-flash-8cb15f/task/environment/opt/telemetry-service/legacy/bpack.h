/*
 * bpack.h - Compact Binary Telemetry Log Format (Version 1)
 */

#ifndef BPACK_H
#define BPACK_H

#include <stdint.h>

#define BPACK_MAGIC "BPK1"
#define BPACK_VERSION 1

#pragma pack(push, 1)

/* 16-byte fixed header for each chunk */
struct bpack_header {
    char magic[4];           /* Must be 'B', 'P', 'K', '1' */
    uint16_t version;        /* Format version, currently 1 */
    uint16_t record_count;   /* Number of records in this chunk */
    uint64_t base_timestamp; /* Base epoch timestamp in milliseconds (little-endian) */
};

/* Record header followed immediately by endpoint string (not null-terminated) */
struct bpack_record {
    int32_t delta_start_ms;  /* Milliseconds offset from base_timestamp */
    uint32_t duration_ms;    /* Task execution duration in milliseconds */
    uint32_t worker_id;      /* Backend worker process/instance identifier */
    int16_t exit_code;       /* Process exit status: 0 for success, non-zero for error */
    uint16_t endpoint_len;   /* Length in bytes of the following endpoint UTF-8 string */
    /* char endpoint[endpoint_len]; */
};

#pragma pack(pop)

#endif /* BPACK_H */
