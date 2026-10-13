#include "recenc.h"
#include <sqlite3.h>
#include <stdlib.h>
#include <string.h>

/*
 * Initialize the database schema.
 * Creates encrypted_records and record_meta tables if they do not exist.
 */
int recenc_db_init(sqlite3 *db) {
    const char *sql =
        "CREATE TABLE IF NOT EXISTS encrypted_records ("
        "  record_id INTEGER PRIMARY KEY,"
        "  blob BLOB NOT NULL"
        ");\n"
        "CREATE TABLE IF NOT EXISTS record_meta ("
        "  record_id INTEGER PRIMARY KEY,"
        "  num_fields INTEGER NOT NULL"
        ");";
    char *errmsg = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &errmsg);
    if (rc != SQLITE_OK) {
        sqlite3_free(errmsg);
        return -1;
    }
    return 0;
}

/*
 * Store an encrypted blob in the database.
 * Replaces any existing record with the same record_id.
 */
int recenc_db_store(sqlite3 *db, uint64_t record_id,
                    const uint8_t *blob, size_t blob_len) {
    const char *sql =
        "INSERT OR REPLACE INTO encrypted_records (record_id, blob)"
        " VALUES (?, ?);";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) return -1;
    sqlite3_bind_int64(stmt, 1, (sqlite3_int64)record_id);
    sqlite3_bind_blob(stmt, 2, blob, (int)blob_len, SQLITE_STATIC);
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    return (rc == SQLITE_DONE) ? 0 : -1;
}

/*
 * Store metadata (num_fields) for a record.
 */
int recenc_db_store_meta(sqlite3 *db, uint64_t record_id, int num_fields) {
    const char *sql =
        "INSERT OR REPLACE INTO record_meta (record_id, num_fields)"
        " VALUES (?, ?);";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) return -1;
    sqlite3_bind_int64(stmt, 1, (sqlite3_int64)record_id);
    sqlite3_bind_int(stmt, 2, num_fields);
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    return (rc == SQLITE_DONE) ? 0 : -1;
}

/*
 * Load an encrypted blob from the database.
 * Caller must free *blob.
 */
int recenc_db_load(sqlite3 *db, uint64_t record_id,
                   uint8_t **blob, size_t *blob_len) {
    const char *sql =
        "SELECT blob FROM encrypted_records WHERE record_id = ?;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) return -1;
    sqlite3_bind_int64(stmt, 1, (sqlite3_int64)record_id);
    rc = sqlite3_step(stmt);
    if (rc != SQLITE_ROW) {
        sqlite3_finalize(stmt);
        return -1;
    }
    int len = sqlite3_column_bytes(stmt, 0);
    const void *data = sqlite3_column_blob(stmt, 0);
    *blob = malloc(len);
    if (!*blob) { sqlite3_finalize(stmt); return -1; }
    memcpy(*blob, data, len);
    *blob_len = (size_t)len;
    sqlite3_finalize(stmt);
    return 0;
}

/*
 * Load num_fields from record_meta.
 */
int recenc_db_load_meta(sqlite3 *db, uint64_t record_id, int *num_fields) {
    const char *sql =
        "SELECT num_fields FROM record_meta WHERE record_id = ?;";
    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) return -1;
    sqlite3_bind_int64(stmt, 1, (sqlite3_int64)record_id);
    rc = sqlite3_step(stmt);
    if (rc != SQLITE_ROW) {
        sqlite3_finalize(stmt);
        return -1;
    }
    *num_fields = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return 0;
}
