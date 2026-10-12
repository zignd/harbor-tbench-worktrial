#ifndef DB_FETCH_H
#define DB_FETCH_H

#include <sqlite3.h>

#define MAX_REGION_ID_LEN 64
#define MAX_REGIONS 32

typedef struct {
    char region_id[MAX_REGION_ID_LEN];
} RegionEntry;

typedef struct {
    double sale_amount;
    char region_id[MAX_REGION_ID_LEN];
    int record_id;
} SalesRecord;

typedef struct {
    SalesRecord *records;
    int count;
    int capacity;
} SalesRecordSet;

/* Open the database. Returns sqlite3 handle or NULL on error. */
sqlite3 *db_open(const char *path);

/* Close the database. */
void db_close(sqlite3 *db);

/* Fetch all distinct region IDs from sales_records.
 * Caller must free regions array. Returns count or -1 on error. */
int db_fetch_distinct_regions(sqlite3 *db, RegionEntry **regions_out);

/* Fetch all sales records for a given region.
 * Caller must free via db_free_records. Returns 0 on success. */
int db_fetch_records_for_region(sqlite3 *db, const char *region_id, SalesRecordSet *rset);

/* Fetch all sales records across all regions. */
int db_fetch_all_records(sqlite3 *db, SalesRecordSet *rset);

/* Free a SalesRecordSet. */
void db_free_records(SalesRecordSet *rset);

/* Check if the weight_cache table has any rows. Returns 1 if populated, 0 if empty, -1 on error. */
int db_weight_cache_populated(sqlite3 *db);

/* Get cached weight for a region. Returns -1.0 if not found. */
double db_get_cached_weight(sqlite3 *db, const char *region_id);

#endif /* DB_FETCH_H */
