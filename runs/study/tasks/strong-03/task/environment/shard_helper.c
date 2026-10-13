#include <stdio.h>
#include <stdint.h>
#include <string.h>

uint32_t fnv1a_32(const char* str) {
    uint32_t hash = 2166136261U;
    while (*str) {
        hash ^= (uint8_t)*str++;
        hash *= 16777619U;
    }
    return hash;
}

int main(int argc, char** argv) {
    if (argc < 2) return 1;
    printf("%u\n", fnv1a_32(argv[1]) % 256);
    return 0;
}
