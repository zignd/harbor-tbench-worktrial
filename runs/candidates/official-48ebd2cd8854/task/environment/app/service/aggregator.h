#ifndef AGGREGATOR_H
#define AGGREGATOR_H

#include "config_parser.h"
#include "db_fetch.h"
#include <sqlite3.h>

#define MAX_AGG_REGIONS 32

typedef struct {
    char region_id[MAX_REGION_ID_LEN];
    double weighted_total;
    double weight_used;
    int record_count;
} RegionSummary;

typedef struct {
    RegionSummary summaries[MAX_AGG_REGIONS];
    int count;
} AggregationResult;

int aggregator_run(sqlite3 *db, const ConfigStore *config,
                   AggregationResult *result);

void aggregator_print_result(const AggregationResult *result);

void aggregator_free_result(AggregationResult *result);

#endif /* AGGREGATOR_H */
