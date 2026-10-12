#ifndef DB_WRITER_H
#define DB_WRITER_H

#include "aggregator.h"
#include "config_parser.h"
#include <sqlite3.h>

/* Write aggregation results into region_summaries table.
 * Clears existing rows before inserting.
 * Returns 0 on success, -1 on error. */
int db_writer_write_summaries(sqlite3 *db, const AggregationResult *result);

/* Populate the weight_cache table with weights from config.
 * Uses a formatting pass for storage normalisation.
 * Returns 0 on success, -1 on error. */
int db_writer_populate_cache(sqlite3 *db, const ConfigStore *config,
                              const AggregationResult *result);

/* Clear all rows from region_summaries. */
int db_writer_clear_summaries(sqlite3 *db);

/* Clear all rows from weight_cache. */
int db_writer_clear_cache(sqlite3 *db);

#endif /* DB_WRITER_H */
