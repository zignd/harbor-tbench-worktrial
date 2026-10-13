#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bpack.h"

static int read_exact(FILE *fp, void *buffer, size_t size)
{
    return fread(buffer, 1, size, fp) == size;
}

static int unpack_file(const char *path)
{
    FILE *fp = fopen(path, "rb");
    struct bpack_file_header header;
    uint32_t index;
    int64_t previous_start = 0;

    if (fp == NULL) {
        fprintf(stderr, "%s: %s\n", path, strerror(errno));
        return 0;
    }
    if (!read_exact(fp, &header, sizeof(header))) {
        fprintf(stderr, "%s: truncated file header\n", path);
        fclose(fp);
        return 0;
    }
    if (memcmp(header.magic, BPACK_MAGIC, 4) != 0 || header.version != BPACK_VERSION) {
        fprintf(stderr, "%s: unsupported pack\n", path);
        fclose(fp);
        return 0;
    }

    printf("FILE %s records=%lu base=%lld\n", path,
           (unsigned long)header.record_count,
           (long long)(BPACK_EPOCH_MS + (int64_t)header.base_timestamp_offset_ms));

    for (index = 0; index < header.record_count; ++index) {
        struct bpack_record_header record;
        char endpoint[8192];
        int64_t duration;
        int64_t start;

        if (!read_exact(fp, &record, sizeof(record)) ||
            record.endpoint_length == 0 ||
            record.endpoint_length > sizeof(endpoint) ||
            !read_exact(fp, endpoint, record.endpoint_length) ||
            !read_exact(fp, &duration, sizeof(duration)) ||
            duration <= 0) {
            fprintf(stderr, "%s: invalid record %lu\n", path, (unsigned long)index);
            fclose(fp);
            return 0;
        }
        start = index == 0
            ? BPACK_EPOCH_MS + (int64_t)header.base_timestamp_offset_ms + (int64_t)record.start_delta_ms
            : previous_start + (int64_t)record.start_delta_ms;
        previous_start = start;
        endpoint[record.endpoint_length] = '\0';
        printf("RECORD %lu endpoint=%s worker=%u start=%lld end=%lld exit=%u\n",
               (unsigned long)index, endpoint, (unsigned)record.worker_id,
               (long long)start, (long long)(start + duration), (unsigned)record.exit_code);
    }

    if (fgetc(fp) != EOF) {
        fprintf(stderr, "%s: trailing data\n", path);
        fclose(fp);
        return 0;
    }
    fclose(fp);
    return 1;
}

int main(int argc, char **argv)
{
    int argument;
    int status = 1;

    if (argc < 2) {
        fprintf(stderr, "usage: unpack_sample FILE [FILE ...]\n");
        return 2;
    }
    status = 1;
    for (argument = 1; argument < argc; ++argument) {
        if (!unpack_file(argv[argument])) {
            status = 0;
        }
    }
    return status ? 0 : 1;
}
