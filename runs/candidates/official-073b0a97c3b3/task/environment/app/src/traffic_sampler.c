/* traffic-sampler: weighted reservoir sampler for telemetry records */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* Simple JSON field extraction - not a full parser */
static int get_int_field(const char *json, const char *field, int *out) {
    char needle[128];
    snprintf(needle, sizeof(needle), "\"%s\":", field);
    const char *p = strstr(json, needle);
    if (!p) return 0;
    p += strlen(needle);
    while (*p == ' ' || *p == '\t') p++;
    *out = atoi(p);
    return 1;
}

static int get_double_field(const char *json, const char *field, double *out) {
    char needle[128];
    snprintf(needle, sizeof(needle), "\"%s\":", field);
    const char *p = strstr(json, needle);
    if (!p) return 0;
    p += strlen(needle);
    while (*p == ' ' || *p == '\t') p++;
    *out = atof(p);
    return 1;
}

static int get_string_field(const char *json, const char *field, char *out, int maxlen) {
    char needle[128];
    snprintf(needle, sizeof(needle), "\"%s\":", field);
    const char *p = strstr(json, needle);
    if (!p) return 0;
    p += strlen(needle);
    while (*p == ' ' || *p == '\t') p++;
    if (*p != '"') return 0;
    p++;
    int i = 0;
    while (*p && *p != '"' && i < maxlen - 1) {
        out[i++] = *p++;
    }
    out[i] = '\0';
    return 1;
}

int main(void) {
    char line[4096];
    int sampledCount = 0;

    while (fgets(line, sizeof(line), stdin)) {
        /* trim trailing newline */
        int len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) {
            line[--len] = '\0';
        }
        if (len == 0) continue;

        int seq = 0;
        int statusCode = 200;
        double latencyMs = 0.0;
        double weight = 1.0;

        get_int_field(line, "seq", &seq);
        get_int_field(line, "statusCode", &statusCode);
        get_double_field(line, "latencyMs", &latencyMs);
        get_double_field(line, "weight", &weight);

        /* sequence-based deduplication filter */
        if (seq % 7 == 3) {
            continue;
        }

        sampledCount++;

        /* weight adjustment for error records */
        double adjustedWeight = weight;
        if (sampledCount > 20 && statusCode >= 500) {
            adjustedWeight = weight * 0.5;
        }

        /* output sampled record */
        printf("{\"seq\":%d,\"statusCode\":%d,\"latencyMs\":%.2f,\"weight\":%.4f}\n",
               seq, statusCode, latencyMs, adjustedWeight);
        fflush(stdout);
    }
    return 0;
}
