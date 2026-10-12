#ifndef AGGREGATOR_H
#define AGGREGATOR_H

#include "db_fetch.h"
#include "config_parser.h"

#define MAX_REGION_SUMMARIES 64

typedef struct {
    char region_id[MAX_REGION_ID_LEN];
    double weighted_total;
    int    record_count;
    double weight_used;
} RegionSummary;

typedef struct {
    RegionSummary summaries[MAX_REGION_SUMMARIES];
    int count;
} SummarySet;

/*
 * Compute per-region weighted totals from the record set.
 * If the weight_cache in the database is populated, weights are read from there.
 * Otherwise, weights are fetched from the config store.
 * Returns 0 on success, -1 on failure.
 */
int aggregator_run(sqlite3 *db,
                   const RecordSet *rset,
                   const ConfigStore *cfg,
                   SummarySet *out);

/* Find a summary entry by region_id. Returns pointer or NULL. */
RegionSummary *summary_find(SummarySet *sset, const char *region_id);

/* Print summaries to stderr for debugging. */
void summary_dump(const SummarySet *sset);

#endif /* AGGREGATOR_H */
