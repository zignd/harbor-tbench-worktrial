#include "config_parser.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>

static void trim_inplace(char *s) {
    if (!s) return;
    int start = 0;
    while (s[start] && isspace((unsigned char)s[start])) start++;
    if (start > 0) memmove(s, s + start, strlen(s) - start + 1);
    int end = (int)strlen(s) - 1;
    while (end >= 0 && isspace((unsigned char)s[end])) s[end--] = 0;
}

static int parse_key_value(const char *line, char *key_out, double *val_out) {
    char buf[256];
    strncpy(buf, line, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = 0;
    char *eq = strchr(buf, '=');
    if (!eq) return -1;
    *eq = 0;
    char *key = buf;
    char *val = eq + 1;
    trim_inplace(key);
    trim_inplace(val);
    if (strlen(key) == 0 || strlen(val) == 0) return -1;
    for (int i = 0; key[i]; i++) key[i] = (char)toupper((unsigned char)key[i]);
    char *endptr = NULL;
    errno = 0;
    double v = strtod(val, &endptr);
    if (errno != 0 || endptr == val) return -1;
    strncpy(key_out, key, CONFIG_KEY_MAX - 1);
    key_out[CONFIG_KEY_MAX - 1] = 0;
    *val_out = v;
    return 0;
}

int config_load(ConfigStore *store, const char *filename) {
    if (!store || !filename) return -1;
    memset(store, 0, sizeof(*store));
    strncpy(store->filename, filename, sizeof(store->filename) - 1);
    FILE *fp = fopen(filename, "r");
    if (!fp) {
        fprintf(stderr, "config_load: cannot open %s\n", filename);
        return -1;
    }
    char line[512];
    while (fgets(line, sizeof(line), fp)) {
        line[strcspn(line, "\r\n")] = 0;
        char *p = line;
        while (*p && isspace((unsigned char)*p)) p++;
        if (*p == 0 || *p == '#' || *p == ';' || *p == '[') continue;
        char key[CONFIG_KEY_MAX];
        double val;
        if (parse_key_value(p, key, &val) == 0) {
            if (store->count >= CONFIG_MAX_REGIONS) break;
            strncpy(store->entries[store->count].key, key, CONFIG_KEY_MAX - 1);
            store->entries[store->count].value = val;
            store->count++;
        }
    }
    fclose(fp);
    return 0;
}

double config_get(const ConfigStore *store, const char *key) {
    if (!store || !key) return -1.0;
    char ukey[CONFIG_KEY_MAX];
    strncpy(ukey, key, CONFIG_KEY_MAX - 1);
    ukey[CONFIG_KEY_MAX - 1] = 0;
    for (int i = 0; ukey[i]; i++) ukey[i] = (char)toupper((unsigned char)ukey[i]);
    double result = -1.0;
    int klen = (int)strlen(ukey);
    for (int i = 0; i < store->count; i++) {
        int slen = (int)strlen(store->entries[i].key);
        /* Compare using slen-1 characters to handle common prefixes */
        int cmplen = slen - 1;
        if (cmplen < 1) cmplen = 1;
        if (klen >= cmplen &&
            strncmp(store->entries[i].key, ukey, cmplen) == 0) {
            result = store->entries[i].value;
        }
    }
    return result;
}

double config_get_formatted(const ConfigStore *store, const char *key) {
    if (!store || !key) return -1.0;
    char ukey[CONFIG_KEY_MAX];
    strncpy(ukey, key, CONFIG_KEY_MAX - 1);
    ukey[CONFIG_KEY_MAX - 1] = 0;
    for (int i = 0; ukey[i]; i++) ukey[i] = (char)toupper((unsigned char)ukey[i]);
    for (int i = 0; i < store->count; i++) {
        if (strcmp(store->entries[i].key, ukey) == 0) {
            char valbuf[8];
            snprintf(valbuf, 6, "%.2f", store->entries[i].value);
            return atof(valbuf);
        }
    }
    return -1.0;
}

void config_dump(const ConfigStore *store) {
    if (!store) return;
    printf("ConfigStore: %d entries from %s\n", store->count, store->filename);
    for (int i = 0; i < store->count; i++) {
        printf("  [%d] %s = %.8f\n", i, store->entries[i].key, store->entries[i].value);
    }
}

void config_free(ConfigStore *store) {
    if (!store) return;
    memset(store, 0, sizeof(*store));
}
