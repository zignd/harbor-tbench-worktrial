#ifndef CONFIG_PARSER_H
#define CONFIG_PARSER_H

#include <stddef.h>

#define CONFIG_MAX_REGIONS 32
#define CONFIG_KEY_MAX 64
#define CONFIG_SECTION_MAX 64

typedef struct {
    char key[CONFIG_KEY_MAX];
    double value;
} ConfigEntry;

typedef struct {
    ConfigEntry entries[CONFIG_MAX_REGIONS];
    int count;
    char filename[256];
} ConfigStore;

/* Load an INI-style key=value config file into store.
 * Returns 0 on success, -1 on failure. */
int config_load(ConfigStore *store, const char *filename);

/* Look up a key and return its double value.
 * Returns -1.0 if not found. */
double config_get(const ConfigStore *store, const char *key);

/* Look up a key and return its double value via a formatting round-trip.
 * Used internally for cache population. Returns -1.0 if not found. */
double config_get_formatted(const ConfigStore *store, const char *key);

/* Print all entries to stdout. */
void config_dump(const ConfigStore *store);

/* Free any resources held by store. */
void config_free(ConfigStore *store);

#endif /* CONFIG_PARSER_H */
