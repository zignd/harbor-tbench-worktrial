#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t load32(const unsigned char *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static uint16_t load16(const unsigned char *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}
static int sync_at(const unsigned char *p) {
    return p[0] == 'M' && p[1] == 'A' && p[2] == 'F' && p[3] == '2';
}
static void inspect(const unsigned char *data, size_t size) {
    size_t count = 0;
    for (size_t i = 0; i + 20 <= size; ++i) {
        if (!sync_at(data + i)) continue;
        uint16_t rows = load16(data + i + 4);
        uint16_t cols = load16(data + i + 6);
        uint32_t sequence = load32(data + i + 8);
        uint32_t length = load32(data + i + 12);
        uint32_t reserved = load32(data + i + 16);
        printf("candidate=%zu rows=%u cols=%u sequence=%" PRIu32 " length=%" PRIu32 " reserved=%" PRIu32 "\n", i, rows, cols, sequence, length, reserved);
        ++count;
    }
    fprintf(stderr, "candidates=%zu bytes=%zu\n", count, size);
}
int main(void) {
    unsigned char *data = NULL;
    size_t used = 0, capacity = 0;
    for (;;) {
        if (used == capacity) {
            size_t next = capacity ? capacity * 2 : 4096;
            unsigned char *grown = realloc(data, next);
            if (!grown) { free(data); return 2; }
            data = grown; capacity = next;
        }
        size_t got = fread(data + used, 1, capacity - used, stdin);
        used += got;
        if (got == 0) break;
    }
    if (ferror(stdin)) { fprintf(stderr, "read: %s\n", strerror(errno)); free(data); return 2; }
    inspect(data, used);
    free(data);
    return 0;
}
