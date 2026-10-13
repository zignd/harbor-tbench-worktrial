#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "config.h"

void load_config(const char *path, config_t *cfg) {
    cfg->buffer_size = 1024;
    cfg->secure_mode = 0;
    FILE *f = fopen(path, "r");
    if (!f) return;
    char line[256];
    while (fgets(line, sizeof(line), f)) {
        char *key = strtok(line, ": ");
        char *value = strtok(NULL, "\n\r ");
        if (key && value) {
            if (strcmp(key, "buffer_size") == 0) cfg->buffer_size = atoi(value);
            if (strcmp(key, "secure_mode") == 0) {
                if (strcmp(value, "true") == 0) cfg->secure_mode = 1;
            }
        }
    }
    fclose(f);
}
