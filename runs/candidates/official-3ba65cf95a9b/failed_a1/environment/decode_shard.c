#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

/*
 * Telemetry Shard Decoder v2.4.1
 * Protocol Specification: TLM_SHARD_V2
 *
 * Header: 16 bytes
 *   - Magic: 'TLMSHRD1' (8 bytes)
 *   - Record count: uint32_t (4 bytes)
 *   - Reserved: uint32_t (4 bytes)
 *
 * Flags bitmask definitions:
 *   0x01 : INFRA_FAULT            (Runner abort, host crash, or network timeout)
 *   0x02 : SPECULATIVE_EXECUTION  (Tentative speculative run)
 *   0x04 : SUPERSEDED             (Cancelled or superseded execution)
 */

static const char *FLAG_INFRA_FAULT = "INFRA_FAULT";
static const char *FLAG_SPECULATIVE = "SPECULATIVE_EXECUTION";
static const char *FLAG_SUPERSEDED  = "SUPERSEDED/ABORTED";

#pragma pack(push, 1)
typedef struct {
    uint64_t record_id;
    char commit_hash[16];
    char test_name[64];
    char runner_pool[24];
    uint8_t outcome;
    uint32_t duration_us;
    uint8_t flags;
    uint64_t timestamp;
} ShardRecord;
#pragma pack(pop)

static const char* outcome_str(uint8_t o) {
    switch (o) {
        case 0: return "PASSED";
        case 1: return "FAILED";
        case 2: return "SKIPPED";
        default: return "UNKNOWN";
    }
}

void print_usage(const char *prog) {
    fprintf(stderr, "Usage: %s [--help] <shard_file.dat>\n", prog);
    fprintf(stderr, "Decodes binary telemetry shards to tab-separated values.\n");
    fprintf(stderr, "Columns: record_id, commit_hash, test_name, runner_pool, outcome, duration_us, flags, timestamp\n");
    fprintf(stderr, "Flag definitions: 0x01=INFRA_FAULT, 0x02=SPECULATIVE_EXECUTION, 0x04=SUPERSEDED\n");
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }
    if (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
        print_usage(argv[0]);
        return 0;
    }

    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        perror("Failed to open file");
        return 1;
    }

    char magic[8];
    if (fread(magic, 1, 8, f) != 8 || memcmp(magic, "TLMSHRD1", 8) != 0) {
        fprintf(stderr, "Error: Invalid shard magic header in %s\n", argv[1]);
        fclose(f);
        return 2;
    }

    uint32_t count = 0;
    uint32_t reserved = 0;
    if (fread(&count, sizeof(uint32_t), 1, f) != 1 ||
        fread(&reserved, sizeof(uint32_t), 1, f) != 1) {
        fprintf(stderr, "Error: Truncated header in %s\n", argv[1]);
        fclose(f);
        return 2;
    }

    char out_buf[65536];
    setvbuf(stdout, out_buf, _IOFBF, sizeof(out_buf));

    ShardRecord rec;
    for (uint32_t i = 0; i < count; i++) {
        if (fread(&rec, sizeof(ShardRecord), 1, f) != 1) {
            fprintf(stderr, "Error: Unexpected EOF at record %u/%u\n", i, count);
            fclose(f);
            return 3;
        }
        rec.commit_hash[sizeof(rec.commit_hash) - 1] = '\0';
        rec.test_name[sizeof(rec.test_name) - 1] = '\0';
        rec.runner_pool[sizeof(rec.runner_pool) - 1] = '\0';

        printf("%llu\t%s\t%s\t%s\t%s\t%u\t%u\t%llu\n",
            (unsigned long long)rec.record_id,
            rec.commit_hash,
            rec.test_name,
            rec.runner_pool,
            outcome_str(rec.outcome),
            rec.duration_us,
            rec.flags,
            (unsigned long long)rec.timestamp
        );
    }

    fclose(f);
    return 0;
}
