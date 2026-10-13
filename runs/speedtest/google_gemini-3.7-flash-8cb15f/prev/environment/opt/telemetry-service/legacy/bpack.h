#ifndef BPACK_H
#define BPACK_H

#include <stdint.h>

#define BPACK_MAGIC "BPK1"

#pragma pack(push, 1)

typedef struct {
    char magic[4];             /* Must be 'BPK1' */
    uint32_t chunk_count;      /* Little-endian number of chunks */
    uint64_t base_timestamp_ms;/* Little-endian base epoch timestamp in ms */
} bpack_file_header_t;

typedef struct {
    uint32_t worker_id;        /* Little-endian backend worker identifier */
    uint32_t record_count;     /* Little-endian number of records in this chunk */
} bpack_chunk_header_t;

typedef struct {
    int32_t delta_start_ms;    /* Little-endian signed millisecond delta from base_timestamp_ms */
    uint32_t duration_ms;      /* Little-endian duration in ms (execution interval: [base + delta, base + delta + duration]) */
    uint16_t worker_exit_code; /* Little-endian exit code (0: OK, >0: error/failure) */
    uint16_t endpoint_len;     /* Little-endian length of endpoint string in bytes */
    /* Followed immediately by endpoint_len bytes of UTF-8 endpoint string (not null-terminated) */
} bpack_record_header_t;

#pragma pack(pop)

#endif /* BPACK_H */
