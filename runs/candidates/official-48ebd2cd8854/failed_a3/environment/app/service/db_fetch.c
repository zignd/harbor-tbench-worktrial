
#include "db_fetch.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlite3.h>

sqlite3 *db_open(const char *path) {
    sqlite3 *db = NULL;
    int rc = sqlite3_open(path, &db);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_open: cannot open database '%s': %s\n",
                path, sqlite3_errmsg(db));
        sqlite3_close(db);
        return NULL;
    }
    /* Enable WAL mode for better concurrent access */
    sqlite3_exec(db, "PRAGMA journal_mode=WAL;", NULL, NULL, NULL);
    sqlite3_exec(db, "PRAGMA synchronous=NORMAL;", NULL, NULL, NULL);
    return db;
}

void db_close(sqlite3 *db) {
    if (db) sqlite3_close(db);
}

int db_fetch_distinct_regions(sqlite3 *db, RegionEntry **regions_out) {
    if (!db || !regions_out) return -1;

    const char *sql = "SELECT DISTINCT region_id FROM sales_records ORDER BY region_id ASC;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_fetch_distinct_regions: prepare failed: %s\n", sqlite3_errmsg(db));
        return -1;
    }

    RegionEntry *regions = NULL;
    int count = 0;
    int capacity = 16;
    regions = (RegionEntry *)malloc(sizeof(RegionEntry) * capacity);
    if (!regions) {
        sqlite3_finalize(stmt);
        return -1;
    }

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        if (count >= capacity) {
            capacity *= 2;
            RegionEntry *tmp = (RegionEntry *)realloc(regions, sizeof(RegionEntry) * capacity);
            if (!tmp) { free(regions); sqlite3_finalize(stmt); return -1; }
            regions = tmp;
        }
        const char *rid = (const char *)sqlite3_column_text(stmt, 0);
        if (rid) {
            strncpy(regions[count].region_id, rid, MAX_REGION_ID_LEN - 1);
            regions[count].region_id[MAX_REGION_ID_LEN - 1] = '\0';
            count++;
        }
    }
    sqlite3_finalize(stmt);

    *regions_out = regions;
    return count;
}

static int rset_grow(SalesRecordSet *rset) {
    int new_cap = rset->capacity ? rset->capacity * 2 : 256;
    SalesRecord *tmp = (SalesRecord *)realloc(rset->records, sizeof(SalesRecord) * new_cap);
    if (!tmp) return -1;
    rset->records = tmp;
    rset->capacity = new_cap;
    return 0;
}

int db_fetch_records_for_region(sqlite3 *db, const char *region_id, SalesRecordSet *rset) {
    if (!db || !region_id || !rset) return -1;
    rset->records = NULL;
    rset->count = 0;
    rset->capacity = 0;

    const char *sql = "SELECT record_id, region_id, sale_amount FROM sales_records WHERE region_id = ? ORDER BY record_id ASC;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_fetch_records_for_region: prepare failed: %s\n", sqlite3_errmsg(db));
        return -1;
    }
    sqlite3_bind_text(stmt, 1, region_id, -1, SQLITE_STATIC);

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        if (rset->count >= rset->capacity) {
            if (rset_grow(rset) != 0) {
                sqlite3_finalize(stmt);
                free(rset->records);
                rset->records = NULL;
                return -1;
            }
        }
        SalesRecord *rec = &rset->records[rset->count];
        rec->record_id = sqlite3_column_int(stmt, 0);
        const char *rid = (const char *)sqlite3_column_text(stmt, 1);
        if (rid) {
            strncpy(rec->region_id, rid, MAX_REGION_ID_LEN - 1);
            rec->region_id[MAX_REGION_ID_LEN - 1] = '\0';
        }
        rec->sale_amount = sqlite3_column_double(stmt, 2);
        rset->count++;
    }
    sqlite3_finalize(stmt);
    return 0;
}

int db_fetch_all_records(sqlite3 *db, SalesRecordSet *rset) {
    if (!db || !rset) return -1;
    rset->records = NULL;
    rset->count = 0;
    rset->capacity = 0;

    const char *sql = "SELECT record_id, region_id, sale_amount FROM sales_records ORDER BY region_id, record_id ASC;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "db_fetch_all_records: prepare failed: %s\n", sqlite3_errmsg(db));
        return -1;
    }

    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        if (rset->count >= rset->capacity) {
            if (rset_grow(rset) != 0) {
                sqlite3_finalize(stmt);
                free(rset->records);
                rset->records = NULL;
                return -1;
            }
        }
        SalesRecord *rec = &rset->records[rset->count];
        rec->record_id = sqlite3_column_int(stmt, 0);
        const char *rid = (const char *)sqlite3_column_text(stmt, 1);
        if (rid) {
            strncpy(rec->region_id, rid, MAX_REGION_ID_LEN - 1);
            rec->region_id[MAX_REGION_ID_LEN - 1] = '\0';
        }
        rec->sale_amount = sqlite3_column_double(stmt, 2);
        rset->count++;
    }
    sqlite3_finalize(stmt);
    return 0;
}

void db_free_records(SalesRecordSet *rset) {
    if (!rset) return;
    free(rset->records);
    rset->records = NULL;
    rset->count = 0;
    rset->capacity = 0;
}

int db_weight_cache_populated(sqlite3 *db) {
    if (!db) return -1;
    const char *sql = "SELECT COUNT(*) FROM weight_cache;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) return -1;
    rc = sqlite3_step(stmt);
    int cnt = 0;
    if (rc == SQLITE_ROW) cnt = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return (cnt > 0) ? 1 : 0;
}

double db_get_cached_weight(sqlite3 *db, const char *region_id) {
    if (!db || !region_id) return -1.0;
    const char *sql = "SELECT weight FROM weight_cache WHERE region_id = ?;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) return -1.0;
    sqlite3_bind_text(stmt, 1, region_id, -1, SQLITE_STATIC);
    double w = -1.0;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        w = sqlite3_column_double(stmt, 0);
    }
    sqlite3_finalize(stmt);
    return w;
}
