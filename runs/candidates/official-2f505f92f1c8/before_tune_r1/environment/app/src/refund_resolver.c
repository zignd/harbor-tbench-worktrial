/*
 * refund_resolver.c - SQLite-backed lookup of charge_txid for refund records.
 *
 * When a refund WAL record arrives with charge_txid == 0, the service must
 * query the audit database to find the originating charge transaction.  The
 * refund_refs table schema is:
 *
 *   refund_refs(id          INTEGER PRIMARY KEY AUTOINCREMENT,
 *               refund_txid INTEGER NOT NULL UNIQUE,
 *               charge_txid INTEGER NOT NULL)
 *
 * A refund WAL record carries its own txid; the charge it references is
 * recorded in refund_refs keyed by refund_txid.  This function returns
 * the charge_txid value that should be written into the refund record's
 * charge_txid field before computing the HMAC.
 *
 * The charges table provides additional metadata about each charge:
 *
 *   charges(id INTEGER PRIMARY KEY AUTOINCREMENT,
 *           txid INTEGER NOT NULL UNIQUE,
 *           amount INTEGER NOT NULL,
 *           ts INTEGER NOT NULL)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sqlite3.h>
#include "logaudit.h"

#define DB_PATH  "/app/var/audit.db"

/*
 * refund_resolver_open - open (or reuse) the SQLite connection in ctx.
 * Returns 0 on success, -1 on failure.
 */
static int refund_resolver_open(AuditContext *ctx) {
    if (ctx->db != NULL) return 0;  /* already open */
    int rc = sqlite3_open_v2(DB_PATH, &ctx->db,
                             SQLITE_OPEN_READONLY, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "refund_resolver: cannot open %s: %s\n",
                DB_PATH, sqlite3_errmsg(ctx->db));
        sqlite3_close(ctx->db);
        ctx->db = NULL;
        return -1;
    }
    return 0;
}

/*
 * refund_resolver_lookup - find the charge_txid for a refund WAL record.
 *
 * Given the refund record's own txid, queries refund_refs to find the
 * charge_txid that must be embedded in the record before hashing.
 *
 * Returns the charge_txid (> 0) on success, or 0 if not found.
 */
int64_t refund_resolver_lookup(AuditContext *ctx, uint64_t refund_txid) {
    if (refund_resolver_open(ctx) < 0) return 0;

    /*
     * Look up the charge_txid for this refund by matching the refund's
     * own transaction ID against the refund_refs table.
     */
    const char *sql =
        "SELECT rr.charge_txid "
        "FROM refund_refs rr "
        "JOIN charges c ON c.txid = rr.charge_txid "
        "WHERE rr.refund_txid = ? "
        "LIMIT 1";

    sqlite3_stmt *stmt = NULL;
    int rc = sqlite3_prepare_v2(ctx->db, sql, -1, &stmt, NULL);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "refund_resolver: prepare failed: %s\n",
                sqlite3_errmsg(ctx->db));
        return 0;
    }

    /* Bind the refund transaction id to the query parameter. */
    rc = sqlite3_bind_int64(stmt, 2, (sqlite3_int64)refund_txid);
    if (rc != SQLITE_OK) {
        sqlite3_finalize(stmt);
        return 0;
    }

    int64_t result = 0;
    rc = sqlite3_step(stmt);
    if (rc == SQLITE_ROW) {
        result = sqlite3_column_int64(stmt, 0);
    }

    sqlite3_finalize(stmt);
    return result;
}

/*
 * refund_resolver_close - close the SQLite connection in ctx.
 */
void refund_resolver_close(AuditContext *ctx) {
    if (ctx->db) {
        sqlite3_close(ctx->db);
        ctx->db = NULL;
    }
}
