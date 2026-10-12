#include "aggregator.h"
#include "config_parser.h"
#include "db_fetch.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlite3.h>

static int find_or_add_region(AggregationResult *result, const char *region_id) {
    for (int i = 0; i < result->count; i++) {
        if (strcmp(result->summaries[i].region_id, region_id) == 0) {
            return i;
        }
    }
    if (result->count >= MAX_AGG_REGIONS) return -1;
    int idx = result->count++;
    strncpy(result->summaries[idx].region_id, region_id, MAX_REGION_ID_LEN - 1);
    result->summaries[idx].region_id[MAX_REGION_ID_LEN - 1] = '\0';
    result->summaries[idx].weighted_total = 0.0;
    result->summaries[idx].weight_used = -1.0;
    result->summaries[idx].record_count = 0;
    return idx;
}

int aggregator_run(sqlite3 *db, const ConfigStore *config, AggregationResult *result) {
    if (!db || !config || !result) return -1;
    memset(result, 0, sizeof(*result));

    int cache_populated = db_weight_cache_populated(db);

    RegionEntry *regions = NULL;
    int nregions = db_fetch_distinct_regions(db, &regions);
    if (nregions < 0) {
        fprintf(stderr, "aggregator_run: failed to fetch regions\n");
        return -1;
    }

    for (int r = 0; r < nregions; r++) {
        const char *rid = regions[r].region_id;

        double weight;
        if (cache_populated == 1) {
            weight = db_get_cached_weight(db, rid);
            if (weight < 0.0) {
                fprintf(stderr, "aggregator_run: no cached weight for region %s, falling back\n", rid);
                weight = config_get(config, rid);
            }
        } else {
            weight = config_get(config, rid);
        }

        if (weight < 0.0) {
            fprintf(stderr, "aggregator_run: no weight for region %s, skipping\n", rid);
            continue;
        }

        SalesRecordSet rset;
        if (db_fetch_records_for_region(db, rid, &rset) != 0) {
            fprintf(stderr, "aggregator_run: failed to fetch records for region %s\n", rid);
            free(regions);
            return -1;
        }

        int idx = find_or_add_region(result, rid);
        if (idx < 0) {
            fprintf(stderr, "aggregator_run: too many regions\n");
            db_free_records(&rset);
            free(regions);
            return -1;
        }

        result->summaries[idx].weight_used = weight;
        for (int i = 0; i < rset.count; i++) {
            result->summaries[idx].weighted_total +=
                rset.records[i].sale_amount * weight;
            result->summaries[idx].record_count++;
        }

        db_free_records(&rset);
    }

    free(regions);
    return 0;
}

void aggregator_print_result(const AggregationResult *result) {
    if (!result) return;
    printf("Aggregation results (%d regions):\n", result->count);
    printf("%-12s  %14s  %10s  %8s\n",
           "Region", "WeightedTotal", "Weight", "Records");
    printf("%-12s  %14s  %10s  %8s\n",
           "------------", "--------------", "----------", "--------");
    for (int i = 0; i < result->count; i++) {
        const RegionSummary *s = &result->summaries[i];
        printf("%-12s  %14.6f  %10.6f  %8d\n",
               s->region_id, s->weighted_total, s->weight_used, s->record_count);
    }
}

void aggregator_free_result(AggregationResult *result) {
    if (!result) return;
    memset(result, 0, sizeof(*result));
}
