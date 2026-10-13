#ifndef AGGREGATOR_H
#define AGGREGATOR_H

#include <stdbool.h>

typedef struct {
    char data[1024];
    int len;
} LogEntry;

typedef struct {
    int buffer_size;
    int thread_count;
    bool secure_mode;
} Config;

void load_config(const char *filename, Config *config);
void process_log(LogEntry *entry, Config *config);
void compute_hmac(const char *data, int len, char *out_hex);

#endif
