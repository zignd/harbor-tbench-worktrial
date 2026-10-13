#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "bpack.h"

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <file.bpack>\n", argv[0]);
        return 1;
    }

    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        perror("fopen");
        return 1;
    }

    bpack_file_header_t fhdr;
    if (fread(&fhdr, sizeof(fhdr), 1, f) != 1) {
        fprintf(stderr, "Failed to read file header\n");
        fclose(f);
        return 1;
    }

    if (memcmp(fhdr.magic, "BPK1", 4) != 0) {
        fprintf(stderr, "Invalid magic\n");
        fclose(f);
        return 1;
    }

    printf("File Header: version=%u chunks=%u total_records=%u\n",
           fhdr.version, fhdr.chunk_count, fhdr.total_records);

    uint32_t total_read = 0;
    for (uint32_t c = 0; c < fhdr.chunk_count; c++) {
        bpack_chunk_header_t chdr;
        if (fread(&chdr, sizeof(chdr), 1, f) != 1) {
            fprintf(stderr, "Failed to read chunk header %u\n", c);
            break;
        }

        printf(" Chunk %u: records=%u base_ts=%llu data_bytes=%u\n",
               c, chdr.chunk_records, (unsigned long long)chdr.base_timestamp_ms, chdr.chunk_bytes);

        for (uint32_t r = 0; r < chdr.chunk_records; r++) {
            bpack_record_header_t rec;
            if (fread(&rec, sizeof(rec), 1, f) != 1) {
                fprintf(stderr, "Failed to read record %u in chunk %u\n", r, c);
                break;
            }

            char endpoint[1024];
            if (rec.endpoint_len >= sizeof(endpoint)) {
                fprintf(stderr, "Endpoint too long\n");
                break;
            }
            if (fread(endpoint, 1, rec.endpoint_len, f) != rec.endpoint_len) {
                fprintf(stderr, "Failed to read endpoint string\n");
                break;
            }
            endpoint[rec.endpoint_len] = '\0';

            uint64_t start_ms = chdr.base_timestamp_ms + rec.start_delta_ms;
            uint64_t end_ms = start_ms + rec.duration_ms;

            if (total_read < 5) {
                printf("  [Record %u] task=%u worker=%u code=%d start=%llu end=%llu ep=%s\n",
                       total_read, rec.task_id, rec.worker_id, rec.exit_code,
                       (unsigned long long)start_ms, (unsigned long long)end_ms, endpoint);
            }
            total_read++;
        }
    }

    printf("Total records parsed: %u\n", total_read);
    fclose(f);
    return 0;
}
