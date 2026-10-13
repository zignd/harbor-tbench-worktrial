#ifndef CONFIG_H
#define CONFIG_H
typedef struct {
    int buffer_size;
    int secure_mode;
} config_t;
void load_config(const char *path, config_t *cfg);
#endif
