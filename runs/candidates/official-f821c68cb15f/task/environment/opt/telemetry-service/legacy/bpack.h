#ifndef BPACK_H
#define BPACK_H

#include <stdint.h>

#pragma pack(push, 1)

/* File Header (16 bytes) */
typedef struct {
    char magic[4];          /* Always "BPK1" */
    uint16_t version;       /* Format version (1) */
    uint16_t chunk_count;   /* Number of chunks contained in this file */
    uint32_t total_records; /* Total record count across all chunks */
    uint32_t flags;         /* Reserved flags (default 0) */
} bpack_file_header_t;

/* Chunk Header (16 bytes) */
typedef struct {
    uint32_t chunk_records;     /* Number of records in this chunk */
    uint32_t chunk_bytes;       /* Byte length of serialized records in this chunk */
    uint64_t base_timestamp_ms; /* Unix epoch start timestamp in milliseconds for chunk */
} bpack_chunk_header_t;

/* Backend Record Header (18 bytes) */
typedef struct {
    uint32_t task_id;        /* Backend execution task identifier */
    uint16_t worker_id;      /* Backend worker node identifier */
    int16_t exit_code;       /* Process exit status: 0 for success, non-zero for error */
    uint32_t start_delta_ms; /* Delta offset: start_time_ms = base_timestamp_ms + start_delta_ms */
    uint32_t duration_ms;    /* Task duration: end_time_ms = start_time_ms + duration_ms */
    uint16_t endpoint_len;   /* Length of endpoint string immediately following this header */
    /* Followed by: char endpoint[endpoint_len] (UTF-8 encoded string, not null-terminated) */
} bpack_record_header_t;

#pragma pack(pop)

#endif /* BPACK_H */
