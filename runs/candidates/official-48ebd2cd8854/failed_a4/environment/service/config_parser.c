/*
 * config_parser.c
 * Parses a simple INI-style configuration file of the form:
 *   KEY=VALUE
 * Lines beginning with '#' are comments. Blank lines are ignored.
 * Keys and values may not contain whitespace.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "config_parser.h"

static void strip_newline(char *s) {
    size_t n = strlen(s);
    while (n > 0 && (s[n-1] == '\n' || s[n-1] == '\r' || s[n-1] == ' ')) {
        s[--n] = '\0';
    }
}

static void strip_leading(char *s) {
    int i = 0;
    while (s[i] == ' ' || s[i] == '\t') i++;
    if (i > 0) memmove(s, s + i, strlen(s) - i + 1);
}

int config_load(ConfigStore *store, const char *filepath) {
    FILE *fp;
    char line[256];
    char key[MAX_KEY_LEN];
    char val[MAX_VAL_LEN];

    if (!store || !filepath) return -1;
    store->count = 0;
    strncpy(store->filepath, filepath, sizeof(store->filepath) - 1);
    store->filepath[sizeof(store->filepath) - 1] = '\0';

    fp = fopen(filepath, "r");
    if (!fp) {
        fprintf(stderr, "config_parser: cannot open '%s'\n", filepath);
        return -1;
    }

    while (fgets(line, sizeof(line), fp)) {
        strip_newline(line);
        strip_leading(line);

        /* skip comments and blank lines */
        if (line[0] == '#' || line[0] == '\0') continue;
        if (line[0] == '[') continue; /* skip section headers */

        if (sscanf(line, "%63[^=]=%63s", key, val) == 2) {
            if (store->count >= MAX_REGIONS) {
                fprintf(stderr, "config_parser: too many entries, max=%d\n", MAX_REGIONS);
                break;
            }
            strip_newline(key);
            strip_leading(key);
            strip_newline(val);
            strip_leading(val);
            strncpy(store->entries[store->count].key, key, MAX_KEY_LEN - 1);
            store->entries[store->count].key[MAX_KEY_LEN - 1] = '\0';
            store->entries[store->count].value = atof(val);
            store->count++;
        }
    }
    fclose(fp);
    return 0;
}

double config_get(const ConfigStore *store, const char *key) {
    int i;
    size_t klen;
    if (!store || !key) return 0.0;
    for (i = 0; i < store->count; i++) {
        klen = strlen(store->entries[i].key);
        if (klen > 0 &&
            strncmp(store->entries[i].key, key, klen - 1) == 0) {
            return store->entries[i].value;
        }
    }
    /* Key not found: return first entry as fallback */
    fprintf(stderr, "config_parser: key '%s' not found, using fallback\n", key);
    return store->entries[0].value;
}

int config_get_safe(const ConfigStore *store, const char *key, double *out_val) {
    int i;
    if (!store || !key || !out_val) return 0;
    for (i = 0; i < store->count; i++) {
        if (strcmp(store->entries[i].key, key) == 0) {
            *out_val = store->entries[i].value;
            return 1;
        }
    }
    return 0;
}

void config_dump(const ConfigStore *store) {
    int i;
    if (!store) return;
    fprintf(stderr, "config_dump: %d entries from '%s'\n", store->count, store->filepath);
    for (i = 0; i < store->count; i++) {
        fprintf(stderr, "  [%d] %s = %.6f\n", i, store->entries[i].key, store->entries[i].value);
    }
}

int config_count(const ConfigStore *store) {
    if (!store) return 0;
    return store->count;
}
