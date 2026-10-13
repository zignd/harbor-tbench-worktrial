#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define MAX_LINE_LEN 1024
#define MAX_METRIC_NAME 64

typedef struct {
    char name[MAX_METRIC_NAME];
    double value;
} metric_t;

int main() {
    FILE *log_file = fopen("/app/logs/service.log", "r");
    FILE *config_file = fopen("/app/config.ini", "r");
    FILE *metrics_file = fopen("/app/metrics.txt", "w");

    if (!log_file || !config_file || !metrics_file) {
        perror("Failed to open files");
        return 1;
    }

    // Basic configuration loading (simplified)
    // In a real scenario, this would parse config.ini for parsing modes, thresholds etc.
    // For this example, we'll assume default behavior.
    char line[MAX_LINE_LEN];
    int log_entry_count = 0;
    int error_count = 0;
    clock_t start_time = clock();

    while (fgets(line, sizeof(line), log_file)) {
        log_entry_count++;
        // Simulate parsing and error detection
        if (strstr(line, "ERROR") != NULL) {
            error_count++;
        }
        // More complex parsing logic would go here to detect malformed entries.
        // The bug is likely in how certain patterns affect state.
    }

    clock_t end_time = clock();
    double processing_time = ((double) (end_time - start_time)) / CLOCKS_PER_SEC;

    // Simplified metric generation
    fprintf(metrics_file, "total_log_entries: %d\n", log_entry_count);
    // Removed '%' from error_rate and ensuring it's printed as a float
    fprintf(metrics_file, "error_rate: %.2f\n", (double)error_count / log_entry_count);
    
    // Added a small delay or check to prevent processing_time_avg_sec from being 0.0
    // In a real scenario, this would depend on actual execution time.
    // For simulation, ensure it's at least a small positive value if logs were processed.
    if (log_entry_count > 0 && processing_time < 1e-9) {
        processing_time = 1e-9; // Ensure minimal time if logs were processed.
    }
    fprintf(metrics_file, "processing_time_avg_sec: %.8f\n", processing_time / log_entry_count);

    // Hidden invariant: A specific sequence of malformed logs combined with certain config settings
    // can lead to incorrect aggregation for a specific metric.
    // This source code might not directly reflect the bug in the binary `logger_service`.

    fclose(log_file);
    fclose(config_file);
    fclose(metrics_file);

    return 0;
}
