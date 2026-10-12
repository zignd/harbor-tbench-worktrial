#ifndef CONFIG_PARSER_H
#define CONFIG_PARSER_H

#define MAX_REGIONS 32
#define MAX_KEY_LEN 64
#define MAX_VAL_LEN 64

typedef struct {
    char key[MAX_KEY_LEN];
    double value;
} ConfigEntry;

typedef struct {
    ConfigEntry entries[MAX_REGIONS];
    int count;
    char filepath[256];
} ConfigStore;

/* Load an INI-style config file (KEY=VALUE lines, # comments, blank lines ok).
 * Returns 0 on success, -1 on failure. */
int config_load(ConfigStore *store, const char *filepath);

/* Look up a key and return its value. Returns 0.0 and logs a warning if not found. */
double config_get(const ConfigStore *store, const char *key);

/* Look up a key into *out_val. Returns 1 if found, 0 if not. */
int config_get_safe(const ConfigStore *store, const char *key, double *out_val);

/* Print all loaded entries (for debug). */
void config_dump(const ConfigStore *store);

/* Return number of entries loaded. */
int config_count(const ConfigStore *store);

#endif /* CONFIG_PARSER_H */
