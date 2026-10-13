#ifndef TELEMETRY_BPACK_H
#define TELEMETRY_BPACK_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BPACK_MAGIC "BPCK"
#define BPACK_VERSION 1u
#define BPACK_FILE_HEADER_SIZE 16u
#define BPACK_RECORD_HEADER_SIZE 16u
#define BPACK_EPOCH_MS ((int64_t)1700000000000LL)

#pragma pack(push, 1)
struct bpack_file_header {
    char     magic[4];
    uint16_t version;
    uint16_t flags;
    uint32_t record_count;
    uint32_t base_timestamp_offset_ms;
};

struct bpack_record_header {
    uint16_t endpoint_length;
    uint16_t flags;
    uint16_t worker_id;
    uint16_t exit_code;
    int64_t  start_delta_ms;
};
#pragma pack(pop)

/* After bpack_record_header comes endpoint_length raw UTF-8 bytes, then an
 * int64_t execution_duration_ms. Start deltas are signed and are relative to
 * the previous decoded start in the same file. */

#ifdef __cplusplus
}
#endif

#endif
