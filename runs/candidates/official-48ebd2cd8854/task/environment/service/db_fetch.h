#ifndef DB_FETCH_H
#define DB_FETCH_H

#include <sqlite3.h>

#define MAX_REGION_ID_LEN 32
#define MAX_RECORDS 8192

typedef struct {
    int record_id;
    char region_id[MAX_REGION_ID_LEN];
    double sale_amount;
} SaleRecord;

typedef struct {
    SaleRecord *records;
    int count;
    int capacity;
} RecordSet;

/* Open a SQLite database. Returns 0 on success, -1 on failure. */
int db_open(sqlite3 **db, const char *path);

/* Close the database. */
void db_close(sqlite3 *db);

/* Fetch all records from sales_records into rset.
 * Caller must free rset->records with db_free_records().
 * Returns 0 on success, -1 on failure. */
int db_fetch_records(sqlite3 *db, RecordSet *rset);

/* Free memory allocated by db_fetch_records. */
void db_free_records(RecordSet *rset);

/* Return list of distinct region_ids present in sales_records.
 * regions must be a char[MAX_REGIONS][MAX_REGION_ID_LEN] array.
 * Returns count, or -1 on error. */
int db_fetch_regions(sqlite3 *db, char regions[][MAX_REGION_ID_LEN], int max_regions);

/* Check if weight_cache table has any rows. Returns 1 if populated, 0 if empty, -1 on error. */
int db_cache_populated(sqlite3 *db);

/* Fetch weight for a region from weight_cache. Returns 0.0 if not found. */
double db_get_cached_weight(sqlite3 *db, const char *region_id);

#endif /* DB_FETCH_H */
