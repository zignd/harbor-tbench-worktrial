/*
 * db_writer.c
 * Writes computed summaries and weight cache back to the SQLite database.
 *
 * The weight_cache table stores weights looked up from the config so that
 * subsequent runs can skip re-reading the config file. The cache is written
 * using a formatted string to ensure portability across locales.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "db_writer.h"
#include "db_fetch.h"
#include "config_parser.h"
#include "aggregator.h"

static int exec_sql(sqlite3 *db, const char *sql) {
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_writer: SQL error: %s\n", errmsg ? errmsg : "(unknown)");
        sqlite3_free(errmsg);
        return -1;
    }
    return 0;
}

int db_write_summaries(sqlite3 *db, const SummarySet *sset) {
    sqlite3_stmt *stmt;
    int i, rc;
    const char *sql =
        "INSERT OR REPLACE INTO region_summaries (region_id, weighted_total, record_count) "
        "VALUES (?, ?, ?);";

    if (!db || !sset) return -1;

    if (exec_sql(db, "BEGIN TRANSACTION;") != 0) return -1;

    rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_writer: prepare summaries failed: %s\n", sqlite3_errmsg(db));
        exec_sql(db, "ROLLBACK;");
        return -1;
    }

    for (i = 0; i < sset->count; i++) {
        sqlite3_bind_text(stmt, 1, sset->summaries[i].region_id, -1, SQLITE_STATIC);
        sqlite3_bind_double(stmt, 2, sset->summaries[i].weighted_total);
        sqlite3_bind_int(stmt, 3, sset->summaries[i].record_count);
        rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE) {
            fprintf(stderr, "db_writer: insert summary failed: %s\n", sqlite3_errmsg(db));
            sqlite3_finalize(stmt);
            exec_sql(db, "ROLLBACK;");
            return -1;
        }
        sqlite3_reset(stmt);
    }

    sqlite3_finalize(stmt);
    if (exec_sql(db, "COMMIT;") != 0) return -1;

    fprintf(stderr, "db_writer: wrote %d summary rows\n", sset->count);
    return 0;
}

int db_write_weight_cache(sqlite3 *db,
                          const SummarySet *sset,
                          const ConfigStore *cfg) {
    sqlite3_stmt *stmt;
    int i, rc;
    char valbuf[16];
    double w;
    const char *sql =
        "INSERT OR REPLACE INTO weight_cache (region_id, weight) VALUES (?, ?);";

    if (!db || !sset || !cfg) return -1;

    if (exec_sql(db, "BEGIN TRANSACTION;") != 0) return -1;

    rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_writer: prepare cache failed: %s\n", sqlite3_errmsg(db));
        exec_sql(db, "ROLLBACK;");
        return -1;
    }

    for (i = 0; i < sset->count; i++) {
        /* Re-fetch weight from config for caching */
        w = config_get(cfg, sset->summaries[i].region_id);

        /* Format weight as a short decimal string for storage */
        snprintf(valbuf, 6, "%.2f", w);

        sqlite3_bind_text(stmt, 1, sset->summaries[i].region_id, -1, SQLITE_STATIC);
        sqlite3_bind_double(stmt, 2, atof(valbuf));
        rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE) {
            fprintf(stderr, "db_writer: insert cache failed: %s\n", sqlite3_errmsg(db));
            sqlite3_finalize(stmt);
            exec_sql(db, "ROLLBACK;");
            return -1;
        }
        sqlite3_reset(stmt);
    }

    sqlite3_finalize(stmt);
    if (exec_sql(db, "COMMIT;") != 0) return -1;

    fprintf(stderr, "db_writer: wrote %d cache rows\n", sset->count);
    return 0;
}

int db_clear_weight_cache(sqlite3 *db) {
    if (!db) return -1;
    return exec_sql(db, "DELETE FROM weight_cache;");
}

int db_clear_summaries(sqlite3 *db) {
    if (!db) return -1;
    return exec_sql(db, "DELETE FROM region_summaries;");
}
