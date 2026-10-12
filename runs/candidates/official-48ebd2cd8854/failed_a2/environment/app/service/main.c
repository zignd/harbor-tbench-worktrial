#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlite3.h>
#include "config_parser.h"
#include "db_fetch.h"
#include "aggregator.h"
#include "db_writer.h"

static void usage(const char *prog) {
    fprintf(stderr, "Usage: %s --db <database> --config <weights.ini> [--verbose]\n", prog);
    fprintf(stderr, "\n");
    fprintf(stderr, "  --db       path to SQLite database\n");
    fprintf(stderr, "  --config   path to weights INI file\n");
    fprintf(stderr, "  --verbose  print detailed output\n");
}

int main(int argc, char *argv[]) {
    const char *db_path = NULL;
    const char *config_path = NULL;
    int verbose = 0;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--db") == 0 && i + 1 < argc) {
            db_path = argv[++i];
        } else if (strcmp(argv[i], "--config") == 0 && i + 1 < argc) {
            config_path = argv[++i];
        } else if (strcmp(argv[i], "--verbose") == 0) {
            verbose = 1;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            usage(argv[0]);
            return 0;
        } else {
            fprintf(stderr, "Unknown option: %s\n", argv[i]);
            usage(argv[0]);
            return 1;
        }
    }

    if (!db_path || !config_path) {
        fprintf(stderr, "Error: --db and --config are required\n");
        usage(argv[0]);
        return 1;
    }

    /* Load configuration */
    ConfigStore config;
    if (config_load(&config, config_path) != 0) {
        fprintf(stderr, "Failed to load config from %s\n", config_path);
        return 1;
    }
    if (verbose) {
        config_dump(&config);
    }

    /* Open database */
    sqlite3 *db = db_open(db_path);
    if (!db) {
        fprintf(stderr, "Failed to open database %s\n", db_path);
        config_free(&config);
        return 1;
    }

    /* Run aggregation (uses weight_cache if populated, else config) */
    AggregationResult result;
    if (aggregator_run(db, &config, &result) != 0) {
        fprintf(stderr, "Aggregation failed\n");
        db_close(db);
        config_free(&config);
        return 1;
    }

    if (verbose) {
        aggregator_print_result(&result);
    }

    /* Write summaries to database */
    if (db_writer_write_summaries(db, &result) != 0) {
        fprintf(stderr, "Failed to write summaries\n");
        aggregator_free_result(&result);
        db_close(db);
        config_free(&config);
        return 1;
    }

    /* Populate weight cache for subsequent runs */
    if (db_writer_populate_cache(db, &config, &result) != 0) {
        fprintf(stderr, "Warning: failed to populate weight cache\n");
    }

    if (verbose) {
        printf("Done. Wrote %d region summaries.\n", result.count);
    }

    aggregator_free_result(&result);
    db_close(db);
    config_free(&config);
    return 0;
}
