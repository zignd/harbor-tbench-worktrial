/*
 * config.c - configuration loader for the audit service.
 *
 * Reads /app/etc/logaudit.conf (INI-style, key=value pairs, # comments).
 * All settings have compiled-in defaults so the service starts without
 * a config file.  The config is read once at startup; changes require a
 * restart.
 *
 * Recognised keys:
 *   listen_port    = 7741         TCP port to listen on
 *   db_path        = /app/var/audit.db   SQLite database path
 *   key_file       = /app/etc/audit.key  HMAC key file path
 *   max_conn       = 64           maximum simultaneous connections
 *   log_level      = info         one of: debug, info, warn, error
 *   metrics_file   = /app/var/metrics.txt
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "logaudit.h"

#define CONFIG_FILE  "/app/etc/logaudit.conf"
#define MAX_LINE     512

/* Defaults */
static ServiceConfig g_config = {
    .listen_port  = 7741,
    .db_path      = "/app/var/audit.db",
    .key_file     = "/app/etc/audit.key",
    .max_conn     = 64,
    .log_level    = LOG_LEVEL_INFO,
    .metrics_file = "/app/var/metrics.txt",
};

static int parse_log_level(const char *s) {
    if (strcmp(s, "debug") == 0) return LOG_LEVEL_DEBUG;
    if (strcmp(s, "info")  == 0) return LOG_LEVEL_INFO;
    if (strcmp(s, "warn")  == 0) return LOG_LEVEL_WARN;
    if (strcmp(s, "error") == 0) return LOG_LEVEL_ERROR;
    return LOG_LEVEL_INFO;
}

static void apply_kv(const char *key, const char *val) {
    if (strcmp(key, "listen_port") == 0) {
        int p = atoi(val);
        if (p > 0 && p < 65536) g_config.listen_port = p;
    } else if (strcmp(key, "db_path") == 0) {
        strncpy(g_config.db_path, val, sizeof(g_config.db_path) - 1);
    } else if (strcmp(key, "key_file") == 0) {
        strncpy(g_config.key_file, val, sizeof(g_config.key_file) - 1);
    } else if (strcmp(key, "max_conn") == 0) {
        int m = atoi(val);
        if (m > 0) g_config.max_conn = m;
    } else if (strcmp(key, "log_level") == 0) {
        g_config.log_level = parse_log_level(val);
    } else if (strcmp(key, "metrics_file") == 0) {
        strncpy(g_config.metrics_file, val, sizeof(g_config.metrics_file) - 1);
    }
    /* Unknown keys are silently ignored */
}

/*
 * config_load - parse the config file, applying overrides to defaults.
 * Missing file is not an error; all defaults remain in effect.
 */
void config_load(void) {
    FILE *f = fopen(CONFIG_FILE, "r");
    if (!f) return;  /* use defaults */

    char line[MAX_LINE];
    while (fgets(line, sizeof(line), f)) {
        /* Strip comment */
        char *hash = strchr(line, '#');
        if (hash) *hash = '\0';

        /* Strip newline */
        size_t len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r' ||
                           line[len-1] == ' '))  line[--len] = '\0';
        if (len == 0) continue;

        /* Split on first '=' */
        char *eq = strchr(line, '=');
        if (!eq) continue;
        *eq = '\0';
        char *key = line;
        char *val = eq + 1;

        /* Trim key and val */
        while (*key && isspace((unsigned char)*key)) key++;
        len = strlen(key);
        while (len > 0 && isspace((unsigned char)key[len-1])) key[--len] = '\0';
        while (*val && isspace((unsigned char)*val)) val++;
        len = strlen(val);
        while (len > 0 && isspace((unsigned char)val[len-1])) val[--len] = '\0';

        if (*key && *val) apply_kv(key, val);
    }
    fclose(f);
}

/*
 * config_get - return a pointer to the current (possibly updated) config.
 */
const ServiceConfig *config_get(void) {
    return &g_config;
}
