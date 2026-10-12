/*
 * main.c
 * CLI harness for the regional sales aggregation service.
 *
 * Usage:
 *   aggregator [--db <path>] [--config <path>] [--verbose] [--clear-cache]
 *
 * Defaults:
 *   --db      /app/data/sales.db
 *   --config  /app/config/weights.ini
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "config_parser.h"
#include "db_fetch.h"
#include "aggregator.h"
#include "db_writer.h"

static void usage(const char *prog) {
    fprintf(stderr, "Usage: %s [--db PATH] [--config PATH] [--verbose] [--clear-cache]\n", prog);
    exit(1);
}

int main(int argc, char *argv[]) {
    const char *db_path     = "/app/data/sales.db";
    const char *config_path = "/app/config/weights.ini";
    int verbose     = 0;
    int clear_cache = 0;
    int i, rc;

    sqlite3    *db   = NULL;
    ConfigStore cfg;
    RecordSet   rset;
    SummarySet  sset;

    /* Parse command-line arguments */
    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--db") == 0 && i + 1 < argc) {
            db_path = argv[++i];
        } else if (strcmp(argv[i], "--config") == 0 && i + 1 < argc) {
            config_path = argv[++i];
        } else if (strcmp(argv[i], "--verbose") == 0) {
            verbose = 1;
        } else if (strcmp(argv[i], "--clear-cache") == 0) {
            clear_cache = 1;
        } else {
            fprintf(stderr, "Unknown argument: %s\n", argv[i]);
            usage(argv[0]);
        }
    }

    fprintf(stderr, "aggregator: db='%s' config='%s'\n", db_path, config_path);

    /* Load configuration */
    rc = config_load(&cfg, config_path);
    if (rc != 0) {
        fprintf(stderr, "aggregator: failed to load config from '%s'\n", config_path);
        return 1;
    }
    fprintf(stderr, "aggregator: loaded %d config entries\n", config_count(&cfg));
    if (verbose) config_dump(&cfg);

    /* Open database */
    rc = db_open(&db, db_path);
    if (rc != 0) {
        fprintf(stderr, "aggregator: failed to open database\n");
        return 1;
    }

    /* Optionally clear the weight cache */
    if (clear_cache) {
        fprintf(stderr, "aggregator: clearing weight cache\n");
        db_clear_weight_cache(db);
    }

    /* Fetch sales records */
    rc = db_fetch_records(db, &rset);
    if (rc != 0) {
        fprintf(stderr, "aggregator: failed to fetch records\n");
        db_close(db);
        return 1;
    }
    fprintf(stderr, "aggregator: fetched %d records\n", rset.count);

    /* Run aggregation */
    rc = aggregator_run(db, &rset, &cfg, &sset);
    if (rc != 0) {
        fprintf(stderr, "aggregator: aggregation failed\n");
        db_free_records(&rset);
        db_close(db);
        return 1;
    }
    if (verbose) summary_dump(&sset);

    /* Write summaries to database */
    rc = db_write_summaries(db, &sset);
    if (rc != 0) {
        fprintf(stderr, "aggregator: failed to write summaries\n");
        db_free_records(&rset);
        db_close(db);
        return 1;
    }

    /* Update weight cache */
    rc = db_write_weight_cache(db, &sset, &cfg);
    if (rc != 0) {
        fprintf(stderr, "aggregator: failed to update weight cache\n");
        db_free_records(&rset);
        db_close(db);
        return 1;
    }

    db_free_records(&rset);
    db_close(db);

    fprintf(stderr, "aggregator: done\n");
    return 0;
}
