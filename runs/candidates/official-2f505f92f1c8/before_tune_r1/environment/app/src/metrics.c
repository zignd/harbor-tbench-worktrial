/*
 * metrics.c - lightweight operational metrics for the audit service.
 *
 * Tracks per-process counters: connections accepted, records processed,
 * errors encountered, and bytes received.  These are written to a simple
 * text file (/app/var/metrics.txt) on receipt of SIGUSR1 so that an
 * operator can inspect them without interrupting service.
 *
 * None of these counters affect the correctness of audit tags.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <signal.h>
#include <time.h>
#include "logaudit.h"

#define METRICS_FILE  "/app/var/metrics.txt"

/* Global counters - written only from the main thread */
static uint64_t g_connections_total   = 0;
static uint64_t g_records_total       = 0;
static uint64_t g_errors_total        = 0;
static uint64_t g_bytes_received      = 0;
static uint64_t g_refund_lookups      = 0;
static uint64_t g_refund_hits         = 0;
static time_t   g_start_time          = 0;

static volatile int g_dump_requested  = 0;

static void handle_sigusr1(int sig) {
    (void)sig;
    g_dump_requested = 1;
}

/*
 * metrics_init - initialise counters and install SIGUSR1 handler.
 */
void metrics_init(void) {
    g_start_time = time(NULL);
    signal(SIGUSR1, handle_sigusr1);
}

/*
 * metrics_record_connection - called when a new client connects.
 */
void metrics_record_connection(void) {
    g_connections_total++;
}

/*
 * metrics_record_record - called when a WAL record is processed.
 */
void metrics_record_record(size_t bytes) {
    g_records_total++;
    g_bytes_received += bytes;
}

/*
 * metrics_record_error - called when a protocol error occurs.
 */
void metrics_record_error(void) {
    g_errors_total++;
}

/*
 * metrics_record_refund_lookup - called when a refund resolver query runs.
 * hit=1 if the lookup found a row, 0 otherwise.
 */
void metrics_record_refund_lookup(int hit) {
    g_refund_lookups++;
    if (hit) g_refund_hits++;
}

/*
 * metrics_maybe_dump - check if a dump was requested and write to file.
 * Should be called from the main loop between connections.
 */
void metrics_maybe_dump(void) {
    if (!g_dump_requested) return;
    g_dump_requested = 0;

    FILE *f = fopen(METRICS_FILE, "w");
    if (!f) return;

    time_t now     = time(NULL);
    time_t elapsed = now - g_start_time;

    fprintf(f, "uptime_seconds=%lld\n",   (long long)elapsed);
    fprintf(f, "connections_total=%llu\n", (unsigned long long)g_connections_total);
    fprintf(f, "records_total=%llu\n",     (unsigned long long)g_records_total);
    fprintf(f, "errors_total=%llu\n",      (unsigned long long)g_errors_total);
    fprintf(f, "bytes_received=%llu\n",    (unsigned long long)g_bytes_received);
    fprintf(f, "refund_lookups=%llu\n",    (unsigned long long)g_refund_lookups);
    fprintf(f, "refund_hits=%llu\n",       (unsigned long long)g_refund_hits);
    fclose(f);
}

/*
 * metrics_summary - write a one-line summary to stderr for diagnostics.
 */
void metrics_summary(void) {
    fprintf(stderr,
            "metrics: conn=%llu rec=%llu err=%llu bytes=%llu "
            "refund_lookups=%llu hits=%llu\n",
            (unsigned long long)g_connections_total,
            (unsigned long long)g_records_total,
            (unsigned long long)g_errors_total,
            (unsigned long long)g_bytes_received,
            (unsigned long long)g_refund_lookups,
            (unsigned long long)g_refund_hits);
}
