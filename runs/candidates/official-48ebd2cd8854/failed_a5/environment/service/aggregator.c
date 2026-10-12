/*
 * aggregator.c
 * Computes per-region weighted sales totals.
 *
 * Weight lookup strategy:
 *   1. If weight_cache table is populated, read weights from there (warm path).
 *   2. Otherwise, look up weights from the config store (cold path).
 *
 * This two-path design allows the service to avoid re-reading config on
 * repeated runs once the cache is warm.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "aggregator.h"
#include "db_fetch.h"
#include "config_parser.h"

static int find_or_create(SummarySet *sset, const char *region_id) {
    int i;
    for (i = 0; i < sset->count; i++) {
        if (strcmp(sset->summaries[i].region_id, region_id) == 0)
            return i;
    }
    if (sset->count >= MAX_REGION_SUMMARIES) {
        fprintf(stderr, "aggregator: too many regions (max %d)\n", MAX_REGION_SUMMARIES);
        return -1;
    }
    strncpy(sset->summaries[sset->count].region_id, region_id, MAX_REGION_ID_LEN - 1);
    sset->summaries[sset->count].region_id[MAX_REGION_ID_LEN - 1] = '\0';
    sset->summaries[sset->count].weighted_total = 0.0;
    sset->summaries[sset->count].record_count   = 0;
    sset->summaries[sset->count].weight_used    = 0.0;
    return sset->count++;
}

int aggregator_run(sqlite3 *db,
                   const RecordSet *rset,
                   const ConfigStore *cfg,
                   SummarySet *out) {
    int i, idx;
    int use_cache;
    double weight;

    if (!db || !rset || !cfg || !out) return -1;

    out->count = 0;

    /* Determine whether to use warm cache or cold config path */
    use_cache = db_cache_populated(db);
    if (use_cache < 0) {
        fprintf(stderr, "aggregator: cache check failed, using config\n");
        use_cache = 0;
    }

    if (use_cache) {
        fprintf(stderr, "aggregator: warm path — reading weights from weight_cache\n");
    } else {
        fprintf(stderr, "aggregator: cold path — reading weights from config\n");
    }

    for (i = 0; i < rset->count; i++) {
        const SaleRecord *rec = &rset->records[i];

        if (use_cache) {
            weight = db_get_cached_weight(db, rec->region_id);
            if (weight == 0.0) {
                /* Cache miss for this region — fall back to config */
                weight = config_get(cfg, rec->region_id);
            }
        } else {
            weight = config_get(cfg, rec->region_id);
        }

        idx = find_or_create(out, rec->region_id);
        if (idx < 0) return -1;

        out->summaries[idx].weighted_total += rec->sale_amount * weight;
        out->summaries[idx].record_count++;
        out->summaries[idx].weight_used = weight;
    }

    fprintf(stderr, "aggregator: computed summaries for %d regions\n", out->count);
    return 0;
}

RegionSummary *summary_find(SummarySet *sset, const char *region_id) {
    int i;
    if (!sset || !region_id) return NULL;
    for (i = 0; i < sset->count; i++) {
        if (strcmp(sset->summaries[i].region_id, region_id) == 0)
            return &sset->summaries[i];
    }
    return NULL;
}

void summary_dump(const SummarySet *sset) {
    int i;
    if (!sset) return;
    fprintf(stderr, "summary_dump: %d regions\n", sset->count);
    for (i = 0; i < sset->count; i++) {
        fprintf(stderr, "  %s: total=%.6f count=%d weight=%.6f\n",
                sset->summaries[i].region_id,
                sset->summaries[i].weighted_total,
                sset->summaries[i].record_count,
                sset->summaries[i].weight_used);
    }
}
