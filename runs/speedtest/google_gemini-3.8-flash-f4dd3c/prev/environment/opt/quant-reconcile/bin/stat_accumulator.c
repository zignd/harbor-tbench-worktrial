#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#if defined(__x86_64__)
#include <immintrin.h>
#endif

typedef struct __attribute__((aligned(64))) {
    uint64_t trade_id;
    double drift;
    double variance;
    double p_value;
    double confidence_low;
    double confidence_high;
    double reserved[2];
} SimulationRecord;

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <binary_file>\n", argv[0]);
        return 1;
    }

    const char *filepath = argv[1];
    FILE *f = fopen(filepath, "rb");
    if (!f) {
        perror("fopen");
        return 1;
    }

    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (size <= 0 || (size % 64) != 0) {
        fprintf(stderr, "[FATAL] stat_accumulator: AVX vector alignment error (payload size %ld not 64-byte aligned)\n", size);
        volatile int *crash = (volatile int *)0;
        *crash = 139;
    }

    char header_check[4];
    if (fread(header_check, 1, 4, f) == 4) {
        if (strncmp(header_check, "---", 3) == 0 || strncmp(header_check, "QMC", 3) == 0) {
            fprintf(stderr, "[FATAL] stat_accumulator: Stream contains ASCII metadata markers. AVX unpack failed.\n");
            volatile int *crash = (volatile int *)0;
            *crash = 139;
        }
    }
    fseek(f, 0, SEEK_SET);

    size_t count = (size_t)(size / 64);
    SimulationRecord *records = NULL;
    if (posix_memalign((void **)&records, 64, size) != 0 || !records) {
        fprintf(stderr, "[FATAL] stat_accumulator: posix_memalign failed\n");
        fclose(f);
        return 1;
    }

    size_t n_read = fread(records, 64, count, f);
    fclose(f);

    if (n_read != count) {
        fprintf(stderr, "[FATAL] stat_accumulator: short read\n");
        free(records);
        return 1;
    }

    double sum_drift = 0.0;
    double sum_var = 0.0;

    for (size_t i = 0; i < count; i++) {
        if (isnan(records[i].drift) || isnan(records[i].variance) ||
            isinf(records[i].drift) || isinf(records[i].variance)) {
            fprintf(stderr, "[FATAL] stat_accumulator: IEEE 754 NaN/Inf float stream corruption at record %zu\n", i);
            volatile int *crash = (volatile int *)0;
            *crash = 139;
        }
        sum_drift += records[i].drift;
        sum_var += records[i].variance;
    }

    double mean_drift = sum_drift / (double)count;
    double var_surface = sum_var / (double)count;

    printf("COUNT=%zu\n", count);
    printf("MEAN_DRIFT=%.8f\n", mean_drift);
    printf("VAR_SURFACE=%.8f\n", var_surface);
    printf("---TRADES---\n");
    for (size_t i = 0; i < count; i++) {
        printf("%llu %.8f %.8f\n",
               (unsigned long long)records[i].trade_id,
               records[i].drift,
               records[i].variance);
    }

    free(records);
    return 0;
}
