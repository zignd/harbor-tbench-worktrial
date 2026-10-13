#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#define SHARD_MAGIC 0x44524853 /* "SHRD" */

static const char* DECODER_INFO = "Telemetry Shard Decoder v2.4 (CI Aggregator Engine)";
static const char* FLAG_DOCS =
    "Record Flags Bitmask Definitions:\n"
    "  0x01: INFRA_FAULT (runner agent crash, network disconnect, worker node eviction)\n"
    "  0x02: SPECULATIVE_EXECUTION (hedged or speculative test run)\n"
    "  0x04: SUPERSEDED (aborted or superseded speculative run)\n";

#pragma pack(push, 1)
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t record_count;
    uint32_t reserved;
} ShardHeader;

typedef struct {
    uint64_t record_id;
    char commit_hash[16];
    char test_name[64];
    char runner_pool[24];
    char outcome[16];
    uint64_t duration_us;
    uint32_t flags;
    uint64_t timestamp;
    char trace_payload[340];
} ShardRecord;
#pragma pack(pop)

static int process_shard(const char* filepath) {
    FILE* fp = fopen(filepath, "rb");
    if (!fp) {
        fprintf(stderr, "Error: Cannot open shard file: %s\n", filepath);
        return 1;
    }
    ShardHeader hdr;
    if (fread(&hdr, sizeof(ShardHeader), 1, fp) != 1) {
        fprintf(stderr, "Error: Failed to read shard header: %s\n", filepath);
        fclose(fp);
        return 1;
    }
    if (hdr.magic != SHARD_MAGIC) {
        fprintf(stderr, "Error: Invalid magic 0x%08x in shard: %s\n", hdr.magic, filepath);
        fclose(fp);
        return 1;
    }
    ShardRecord rec;
    for (uint32_t i = 0; i < hdr.record_count; i++) {
        if (fread(&rec, sizeof(ShardRecord), 1, fp) != 1) {
            fprintf(stderr, "Error: Unexpected EOF in shard: %s at record %u\n", filepath, i);
            fclose(fp);
            return 1;
        }
        printf("%llu\t%s\t%s\t%s\t%s\t%llu\t%u\t%llu\n",
               (unsigned long long)rec.record_id,
               rec.commit_hash,
               rec.test_name,
               rec.runner_pool,
               rec.outcome,
               (unsigned long long)rec.duration_us,
               rec.flags,
               (unsigned long long)rec.timestamp);
    }
    fclose(fp);
    return 0;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <shard_file> [shard_file2 ...]\n", argv[0]);
        return 1;
    }
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            printf("%s\n\n%s", DECODER_INFO, FLAG_DOCS);
            return 0;
        }
    }
    setvbuf(stdout, NULL, _IOFBF, 1048576);
    for (int i = 1; i < argc; i++) {
        if (process_shard(argv[i]) != 0) return 1;
    }
    fflush(stdout);
    return 0;
}
