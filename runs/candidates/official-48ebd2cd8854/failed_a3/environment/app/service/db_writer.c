#include "db_writer.h"
#include "config_parser.h"
#include "aggregator.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlite3.h>

static int db_exec_simple(sqlite3 *db, const char *sql) {
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_exec_simple failed: %s\n", errmsg);
        sqlite3_free(errmsg);
        return -1;
    }
    return 0;
}

int db_writer_clear_summaries(sqlite3 *db) {
    return db_exec_simple(db, "DELETE FROM region_summaries;");
}

int db_writer_clear_cache(sqlite3 *db) {
    return db_exec_simple(db, "DELETE FROM weight_cache;");
}

int db_writer_write_summaries(sqlite3 *db, const AggregationResult *result) {
    if (!db || !result) return -1;

    if (db_writer_clear_summaries(db) != 0) return -1;

    const char *sql =
        "INSERT INTO region_summaries (region_id, weighted_total, record_count) "
        "VALUES (?, ?, ?);";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_writer_write_summaries: prepare failed: %s\n",
                sqlite3_errmsg(db));
        return -1;
    }

    db_exec_simple(db, "BEGIN TRANSACTION;");
    for (int i = 0; i < result->count; i++) {
        const RegionSummary *s = &result->summaries[i];
        sqlite3_reset(stmt);
        sqlite3_bind_text(stmt, 1, s->region_id, -1, SQLITE_STATIC);
        sqlite3_bind_double(stmt, 2, s->weighted_total);
        sqlite3_bind_int(stmt, 3, s->record_count);
        rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE) {
            fprintf(stderr, "db_writer_write_summaries: insert failed for region %s: %s\n",
                    s->region_id, sqlite3_errmsg(db));
            sqlite3_finalize(stmt);
            db_exec_simple(db, "ROLLBACK;");
            return -1;
        }
    }
    db_exec_simple(db, "COMMIT;");
    sqlite3_finalize(stmt);
    return 0;
}

int db_writer_populate_cache(sqlite3 *db, const ConfigStore *config,
                              const AggregationResult *result) {
    if (!db || !config || !result) return -1;

    if (db_writer_clear_cache(db) != 0) return -1;

    const char *sql =
        "INSERT INTO weight_cache (region_id, weight) VALUES (?, ?);";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_writer_populate_cache: prepare failed: %s\n",
                sqlite3_errmsg(db));
        return -1;
    }

    db_exec_simple(db, "BEGIN TRANSACTION;");
    for (int i = 0; i < result->count; i++) {
        const char *rid = result->summaries[i].region_id;
        /* Use formatted lookup to normalise weight for cache storage */
        double w = config_get_formatted(config, rid);
        if (w < 0.0) {
            fprintf(stderr, "db_writer_populate_cache: no weight for region %s\n", rid);
            continue;
        }
        sqlite3_reset(stmt);
        sqlite3_bind_text(stmt, 1, rid, -1, SQLITE_STATIC);
        sqlite3_bind_double(stmt, 2, w);
        rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE) {
            fprintf(stderr, "db_writer_populate_cache: insert failed for %s: %s\n",
                    rid, sqlite3_errmsg(db));
        }
    }
    db_exec_simple(db, "COMMIT;");
    sqlite3_finalize(stmt);
    return 0;
}
