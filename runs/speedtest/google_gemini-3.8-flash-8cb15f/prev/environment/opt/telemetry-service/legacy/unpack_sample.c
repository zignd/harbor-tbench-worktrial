#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "bpack.h"

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <pack_file.bpack>\n", argv[0]);
        return 1;
    }
    FILE *fp = fopen(argv[1], "rb");
    if (!fp) {
        perror("fopen");
        return 1;
    }

    struct bpack_header hdr;
    while (fread(&hdr, sizeof(hdr), 1, fp) == 1) {
        if (memcmp(hdr.magic, BPACK_MAGIC, 4) != 0) {
            fprintf(stderr, "Invalid magic bytes\n");
            fclose(fp);
            return 1;
        }

        printf("Chunk: version=%u, records=%u, base_timestamp=%llu\n",
               hdr.version, hdr.record_count, (unsigned long long)hdr.base_timestamp);

        for (uint16_t i = 0; i < hdr.record_count; i++) {
            struct bpack_record rec;
            if (fread(&rec, sizeof(rec), 1, fp) != 1) {
                fprintf(stderr, "Truncated record %u\n", i);
                break;
            }
            char *ep = malloc(rec.endpoint_len + 1);
            if (fread(ep, 1, rec.endpoint_len, fp) != rec.endpoint_len) {
                fprintf(stderr, "Truncated endpoint string\n");
                free(ep);
                break;
            }
            ep[rec.endpoint_len] = '\0';
            uint64_t start_ms = hdr.base_timestamp + rec.delta_start_ms;
            printf("  [%u] worker=%u start=%llu dur=%u ms exit=%d ep=%s\n",
                   i, rec.worker_id, (unsigned long long)start_ms, rec.duration_ms, rec.exit_code, ep);
            free(ep);
        }
    }

    fclose(fp);
    return 0;
}
