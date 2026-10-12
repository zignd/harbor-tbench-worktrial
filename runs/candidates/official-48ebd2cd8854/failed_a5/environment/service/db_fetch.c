/*
 * db_fetch.c
 * Handles reading sales records and region lists from the SQLite database.
 * Also provides access to the weight_cache table for warm-start lookups.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "db_fetch.h"

int db_open(sqlite3 **db, const char *path) {
    int rc;
    if (!db || !path) return -1;
    rc = sqlite3_open(path, db);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_fetch: cannot open database '%s': %s\n",
                path, sqlite3_errmsg(*db));
        sqlite3_close(*db);
        *db = NULL;
        return -1;
    }
    /* Enable WAL mode for better concurrent access */
    sqlite3_exec(*db, "PRAGMA journal_mode=WAL;", NULL, NULL, NULL);
    sqlite3_exec(*db, "PRAGMA synchronous=NORMAL;", NULL, NULL, NULL);
    return 0;
}

void db_close(sqlite3 *db) {
    if (db) sqlite3_close(db);
}

int db_fetch_records(sqlite3 *db, RecordSet *rset) {
    sqlite3_stmt *stmt;
    int rc;
    const char *sql = "SELECT record_id, region_id, sale_amount FROM sales_records ORDER BY record_id;";

    if (!db || !rset) return -1;

    rset->capacity = 256;
    rset->count = 0;
    rset->records = (SaleRecord *)malloc(rset->capacity * sizeof(SaleRecord));
    if (!rset->records) {
        fprintf(stderr, "db_fetch: out of memory\n");
        return -1;
    }

    rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_fetch: prepare failed: %s\n", sqlite3_errmsg(db));
        free(rset->records);
        rset->records = NULL;
        return -1;
    }

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        if (rset->count >= rset->capacity) {
            rset->capacity *= 2;
            rset->records = (SaleRecord *)realloc(rset->records,
                                                   rset->capacity * sizeof(SaleRecord));
            if (!rset->records) {
                fprintf(stderr, "db_fetch: realloc failed\n");
                sqlite3_finalize(stmt);
                return -1;
            }
        }
        rset->records[rset->count].record_id   = sqlite3_column_int(stmt, 0);
        strncpy(rset->records[rset->count].region_id,
                (const char *)sqlite3_column_text(stmt, 1),
                MAX_REGION_ID_LEN - 1);
        rset->records[rset->count].region_id[MAX_REGION_ID_LEN - 1] = '\0';
        rset->records[rset->count].sale_amount = sqlite3_column_double(stmt, 2);
        rset->count++;
    }

    sqlite3_finalize(stmt);

    if (rc != SQLITE_DONE) {
        fprintf(stderr, "db_fetch: step error: %s\n", sqlite3_errmsg(db));
        free(rset->records);
        rset->records = NULL;
        return -1;
    }

    fprintf(stderr, "db_fetch: loaded %d records\n", rset->count);
    return 0;
}

void db_free_records(RecordSet *rset) {
    if (rset && rset->records) {
        free(rset->records);
        rset->records = NULL;
        rset->count = 0;
        rset->capacity = 0;
    }
}

int db_fetch_regions(sqlite3 *db, char regions[][MAX_REGION_ID_LEN], int max_regions) {
    sqlite3_stmt *stmt;
    int rc, count = 0;
    const char *sql = "SELECT DISTINCT region_id FROM sales_records ORDER BY region_id;";

    if (!db || !regions || max_regions <= 0) return -1;

    rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_fetch: regions prepare failed: %s\n", sqlite3_errmsg(db));
        return -1;
    }

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW && count < max_regions) {
        strncpy(regions[count],
                (const char *)sqlite3_column_text(stmt, 0),
                MAX_REGION_ID_LEN - 1);
        regions[count][MAX_REGION_ID_LEN - 1] = '\0';
        count++;
    }
    sqlite3_finalize(stmt);
    return count;
}

int db_cache_populated(sqlite3 *db) {
    sqlite3_stmt *stmt;
    int rc, result = 0;
    const char *sql = "SELECT COUNT(*) FROM weight_cache;";

    if (!db) return -1;
    rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) return -1;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        result = sqlite3_column_int(stmt, 0) > 0 ? 1 : 0;
    }
    sqlite3_finalize(stmt);
    return result;
}

double db_get_cached_weight(sqlite3 *db, const char *region_id) {
    sqlite3_stmt *stmt;
    int rc;
    double weight = 0.0;
    const char *sql = "SELECT weight FROM weight_cache WHERE region_id = ?;";

    if (!db || !region_id) return 0.0;
    rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) return 0.0;
    sqlite3_bind_text(stmt, 1, region_id, -1, SQLITE_STATIC);
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        weight = sqlite3_column_double(stmt, 0);
    }
    sqlite3_finalize(stmt);
    return weight;
}
