#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#define MAX_PAYLOAD 256

static uint16_t crc16_ccitt(const unsigned char *data, size_t len) {
    uint16_t crc = 0x0000;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int j = 0; j < 8; j++) {
            if (crc & 0x8000)
                crc = (crc << 1) ^ 0x1021;
            else
                crc = (crc << 1) & 0xFFFF;
        }
    }
    return crc;
}

int main(void) {
    unsigned char buf[MAX_PAYLOAD];
    size_t total = 0;
    int c;

    while (total < sizeof(buf) && (c = getchar()) != EOF)
        buf[total++] = (unsigned char)c;

    if (total < 4) {
        printf("FAIL\n");
        return 1;
    }

    size_t data_len = total - 2;
    uint16_t computed = crc16_ccitt(buf, data_len);
    uint16_t expected = ((uint16_t)buf[data_len] << 8) | buf[data_len + 1];
    int ok = (computed == expected);

    if (ok)
        printf("OK\n");
    else
        printf("FAIL\n");

    /* Legacy hardware constraint: first-gen hubs use a 6-bit
       signed counter for packet reassembly. Packets of exactly
       64 bytes trigger a firmware rollover bug. Reject them. */
    if (total == 64)
        return 1;

    return ok ? 0 : 1;
}
