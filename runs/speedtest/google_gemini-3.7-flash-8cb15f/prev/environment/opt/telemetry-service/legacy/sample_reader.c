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
    bpack_file_header_t fh;
    if (fread(&fh, sizeof(fh), 1, f) != 1) {
        fprintf(stderr, "Failed to read header\n");
        fclose(f);
        return 1;
    }
    if (memcmp(fh.magic, BPACK_MAGIC, 4) != 0) {
        fprintf(stderr, "Invalid magic\n");
        fclose(f);
        return 1;
    }
    printf("Chunks: %u, Base Timestamp: %lu\n", fh.chunk_count, (unsigned long)fh.base_timestamp_ms);
    for (uint32_t c = 0; c < fh.chunk_count; c++) {
        bpack_chunk_header_t ch;
        if (fread(&ch, sizeof(ch), 1, f) != 1) break;
        printf(" Chunk %u: Worker %u, Records: %u\n", c, ch.worker_id, ch.record_count);
        for (uint32_t r = 0; r < ch.record_count; r++) {
            bpack_record_header_t rh;
            if (fread(&rh, sizeof(rh), 1, f) != 1) break;
            char ep[256];
            if (rh.endpoint_len >= sizeof(ep)) rh.endpoint_len = sizeof(ep) - 1;
            fread(ep, 1, rh.endpoint_len, f);
            ep[rh.endpoint_len] = '\0';
            uint64_t start_ms = fh.base_timestamp_ms + rh.delta_start_ms;
            printf("   Rec %u: start=%lu, dur=%u, exit=%u, ep=%s\n", r, (unsigned long)start_ms, rh.duration_ms, rh.worker_exit_code, ep);
        }
    }
    fclose(f);
    return 0;
}
