#ifndef DB_WRITER_H
#define DB_WRITER_H

#include <sqlite3.h>
#include "aggregator.h"
#include "config_parser.h"

/*
 * Write region summaries into the region_summaries table.
 * Existing rows for the affected regions are replaced.
 * Returns 0 on success, -1 on failure.
 */
int db_write_summaries(sqlite3 *db, const SummarySet *sset);

/*
 * Populate the weight_cache table with the weights used in the given summaries.
 * This caches the applied weights so subsequent runs can use the warm path.
 * Returns 0 on success, -1 on failure.
 */
int db_write_weight_cache(sqlite3 *db,
                          const SummarySet *sset,
                          const ConfigStore *cfg);

/*
 * Clear all rows from weight_cache.
 * Returns 0 on success, -1 on failure.
 */
int db_clear_weight_cache(sqlite3 *db);

/*
 * Clear all rows from region_summaries.
 * Returns 0 on success, -1 on failure.
 */
int db_clear_summaries(sqlite3 *db);

#endif /* DB_WRITER_H */
