/*
 * Data Processor - Annotated Output Generator
 * Reads a binary input file, processes it line-by-line, and produces
 * an annotated text output with comprehensive statistics, filtering,
 * entropy analysis, and a seed marker for security verification.
 *
 * Usage: processor [options]
 * Options:
 *   -v        Verbose mode
 *   -a        ASCII-only mode
 *   -s SEED   Override seed from command line
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <time.h>
#include <math.h>

#define MAX_LINE 4096
#define MAX_OUTPUT_LINE 8192
#define CONFIG_PATH "/app/config/seed.conf"
#define OUTPUT_PATH "/app/output/annotated.txt"
#define INPUT_PATH "/app/testdata/input.bin"

/* Global statistics */
static unsigned long total_bytes = 0;
static unsigned long total_lines = 0;
static unsigned long printable_lines = 0;
static unsigned long binary_lines = 0;
static unsigned long empty_lines = 0;
static unsigned long comments_detected = 0;
static unsigned long uppercase_lines = 0;
static unsigned long lowercase_lines = 0;
static unsigned long numeric_lines = 0;
static unsigned long mixed_lines = 0;
static unsigned long long_lines = 0;
static unsigned long short_lines = 0;
static unsigned long words_total = 0;
static unsigned long max_line_len = 0;
static unsigned long min_line_len = 0xFFFFFFFF;

/* Character frequency histogram */
static unsigned long char_freq[256];

/* Byte-pair frequency (for common 2-byte sequences) */
static unsigned long pair_freq[256][256];

/* Line length histogram */
static unsigned long len_hist[10];

/* Run-length encoding statistics */
static unsigned long run_counts[256];
static unsigned long total_runs = 0;
static unsigned long max_run_length = 0;

static unsigned long seed_value = 0;
static int verbose_mode = 0;
static int ascii_only_mode = 0;

/* Shannon entropy accumulators */
static double byte_probs[256];

/* Function prototypes */
void init_stats(void);
int read_seed(void);
void parse_args(int argc, char **argv);
int is_printable_line(const unsigned char *buf, int len);
void classify_line(const unsigned char *buf, int len);
int count_words(const unsigned char *buf, int len);
void update_histograms(const unsigned char *buf, int len);
void update_run_statistics(const unsigned char *data, size_t len);
void update_pair_frequencies(const unsigned char *data, size_t len);
void process_input(void);
void write_output(void);
void write_header(FILE *fp);
void write_statistics(FILE *fp);
void write_entropy_report(FILE *fp);
void write_run_report(FILE *fp);
void write_pair_report(FILE *fp);
void write_frequency_report(FILE *fp);
void write_footer(FILE *fp);
const char* line_category(const unsigned char *buf, int len);
double compute_entropy(void);
void print_hex_dump_line(FILE *fp, const unsigned char *buf, int len, int offset);

void init_stats(void) {
    int i, j;
    total_bytes = 0;
    total_lines = 0;
    printable_lines = 0;
    binary_lines = 0;
    empty_lines = 0;
    comments_detected = 0;
    uppercase_lines = 0;
    lowercase_lines = 0;
    numeric_lines = 0;
    mixed_lines = 0;
    long_lines = 0;
    short_lines = 0;
    words_total = 0;
    max_line_len = 0;
    min_line_len = 0xFFFFFFFF;
    max_run_length = 0;
    total_runs = 0;
    for (i = 0; i < 256; i++) {
        char_freq[i] = 0;
        byte_probs[i] = 0.0;
        run_counts[i] = 0;
        for (j = 0; j < 256; j++) {
            pair_freq[i][j] = 0;
        }
    }
    for (i = 0; i < 10; i++) len_hist[i] = 0;
}

void parse_args(int argc, char **argv) {
    int i;
    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-v") == 0) {
            verbose_mode = 1;
        } else if (strcmp(argv[i], "-a") == 0) {
            ascii_only_mode = 1;
        } else if (strcmp(argv[i], "-s") == 0 && i + 1 < argc) {
            seed_value = (unsigned long)atol(argv[i + 1]);
            i++;
        }
    }
}

int read_seed(void) {
    FILE *fp = fopen(CONFIG_PATH, "r");
    if (!fp) {
        fprintf(stderr, "WARNING: Cannot open config file %s, using seed 0\n", CONFIG_PATH);
        seed_value = 0;
        return -1;
    }
    if (fscanf(fp, "%lu", &seed_value) != 1) {
        fprintf(stderr, "WARNING: Invalid seed in config, using 0\n");
        seed_value = 0;
        fclose(fp);
        return -1;
    }
    fclose(fp);
    if (verbose_mode) {
        fprintf(stderr, "Read seed from config: %lu\n", seed_value);
    }
    return 0;
}

int is_printable_line(const unsigned char *buf, int len) {
    int i;
    int printable_count = 0;
    if (len == 0) return 0;
    for (i = 0; i < len; i++) {
        if (buf[i] >= 32 && buf[i] <= 126) printable_count++;
        else if (buf[i] == '\t' || buf[i] == '\r') printable_count++;
    }
    /* Consider printable if at least 80% of characters are printable */
    return (printable_count * 100 / len) >= 80;
}

int count_words(const unsigned char *buf, int len) {
    int i, count = 0;
    int in_word = 0;
    for (i = 0; i < len; i++) {
        if (isspace(buf[i])) {
            in_word = 0;
        } else {
            if (!in_word) {
                count++;
                in_word = 1;
            }
        }
    }
    return count;
}

const char* line_category(const unsigned char *buf, int len) {
    int has_upper = 0, has_lower = 0, has_digit = 0, has_other = 0;
    int i;
    
    if (len == 0) return "EMPTY";
    
    for (i = 0; i < len; i++) {
        if (isupper(buf[i])) has_upper = 1;
        else if (islower(buf[i])) has_lower = 1;
        else if (isdigit(buf[i])) has_digit = 1;
        else if (!isspace(buf[i])) has_other = 1;
    }
    
    if (has_upper && !has_lower && !has_digit && !has_other) return "UPPERCASE";
    if (has_lower && !has_upper && !has_digit && !has_other) return "LOWERCASE";
    if (has_digit && !has_upper && !has_lower && !has_other) return "NUMERIC";
    if ((has_upper || has_lower || has_digit) && !has_other) return "MIXED";
    if (has_other) return "BINARY";
    return "OTHER";
}

void classify_line(const unsigned char *buf, int len) {
    const char *cat = line_category(buf, len);
    
    if (strcmp(cat, "UPPERCASE") == 0) uppercase_lines++;
    else if (strcmp(cat, "LOWERCASE") == 0) lowercase_lines++;
    else if (strcmp(cat, "NUMERIC") == 0) numeric_lines++;
    else if (strcmp(cat, "MIXED") == 0) mixed_lines++;
    else if (strcmp(cat, "BINARY") == 0) binary_lines++;
    else if (strcmp(cat, "EMPTY") == 0) empty_lines++;
    
    if (is_printable_line(buf, len)) printable_lines++;
    
    /* Check for comment-like lines */
    if (len >= 2) {
        if (buf[0] == '/' && buf[1] == '/') comments_detected++;
        else if (buf[0] == '#') comments_detected++;
        else if (buf[0] == ';') comments_detected++;
        else if (buf[0] == '-' && buf[1] == '-') comments_detected++;
        else if (buf[0] == '/' && buf[1] == '*') comments_detected++;
        else if (len >= 5 && buf[0] == 'R' && buf[1] == 'E' && buf[2] == 'M') comments_detected++;
    }
}

void update_run_statistics(const unsigned char *data, size_t len) {
    size_t i;
    unsigned char current_byte;
    unsigned long run_len = 0;
    
    if (len == 0) return;
    
    current_byte = data[0];
    run_len = 1;
    
    for (i = 1; i < len; i++) {
        if (data[i] == current_byte) {
            run_len++;
        } else {
            run_counts[current_byte]++;
            total_runs++;
            if (run_len > max_run_length) max_run_length = run_len;
            current_byte = data[i];
            run_len = 1;
        }
    }
    /* Handle last run */
    run_counts[current_byte]++;
    total_runs++;
    if (run_len > max_run_length) max_run_length = run_len;
}

void update_pair_frequencies(const unsigned char *data, size_t len) {
    size_t i;
    for (i = 0; i < len - 1; i++) {
        pair_freq[data[i]][data[i + 1]]++;
    }
}

void update_histograms(const unsigned char *buf, int len) {
    int i, bucket;
    
    for (i = 0; i < len; i++) {
        char_freq[buf[i]]++;
    }
    
    if (len >= 100) bucket = 9;
    else bucket = len / 10;
    len_hist[bucket]++;
    
    if (len > 80) long_lines++;
    if (len < 20 && len > 0) short_lines++;
    if (len > max_line_len) max_line_len = len;
    if (len < min_line_len) min_line_len = len;
}

void process_input(void) {
    FILE *fp = fopen(INPUT_PATH, "rb");
    unsigned char buf[MAX_LINE];
    int c, pos = 0;
    
    if (!fp) {
        fprintf(stderr, "ERROR: Cannot open input file %s\n", INPUT_PATH);
        exit(1);
    }
    
    if (verbose_mode) {
        fprintf(stderr, "Opening input file: %s\n", INPUT_PATH);
    }
    
    while ((c = fgetc(fp)) != EOF) {
        total_bytes++;
        if (pos < MAX_LINE - 1) {
            buf[pos++] = (unsigned char)c;
        }
        if (c == '\n' || pos >= MAX_LINE - 1) {
            buf[pos] = '\0';
            total_lines++;
            classify_line(buf, pos);
            update_histograms(buf, pos);
            update_run_statistics(buf, pos);
            update_pair_frequencies(buf, pos);
            words_total += count_words(buf, pos);
            pos = 0;
        }
    }
    /* Handle last line if no trailing newline */
    if (pos > 0) {
        buf[pos] = '\0';
        total_lines++;
        classify_line(buf, pos);
        update_histograms(buf, pos);
        update_run_statistics(buf, pos);
        update_pair_frequencies(buf, pos);
        words_total += count_words(buf, pos);
    }
    
    fclose(fp);
    
    if (verbose_mode) {
        fprintf(stderr, "Read %lu bytes in %lu lines\n", total_bytes, total_lines);
    }
}

double compute_entropy(void) {
    int i;
    double entropy = 0.0;
    
    if (total_bytes == 0) return 0.0;
    
    for (i = 0; i < 256; i++) {
        if (char_freq[i] > 0) {
            byte_probs[i] = (double)char_freq[i] / (double)total_bytes;
            entropy -= byte_probs[i] * log2(byte_probs[i]);
        }
    }
    return entropy;
}

void print_hex_dump_line(FILE *fp, const unsigned char *buf, int len, int offset) {
    int i;
    fprintf(fp, "  %08x  ", offset);
    for (i = 0; i < 16; i++) {
        if (i < len) fprintf(fp, "%02x ", buf[i]);
        else fprintf(fp, "   ");
    }
    fprintf(fp, " |");
    for (i = 0; i < 16 && i < len; i++) {
        if (buf[i] >= 32 && buf[i] <= 126) fprintf(fp, "%c", buf[i]);
        else fprintf(fp, ".");
    }
    fprintf(fp, "|\n");
}

void write_header(FILE *fp) {
    time_t now = time(NULL);
    fprintf(fp, "========================================\n");
    fprintf(fp, "  DATA PROCESSOR - ANNOTATED OUTPUT\n");
    fprintf(fp, "========================================\n");
    fprintf(fp, "Generated: %s", ctime(&now));
    fprintf(fp, "Input: %s\n", INPUT_PATH);
    if (ascii_only_mode) {
        fprintf(fp, "Mode: ASCII-only filtering enabled\n");
    }
    fprintf(fp, "\n");
}

void write_statistics(FILE *fp) {
    int i;
    
    fprintf(fp, "----------------------------------------\n");
    fprintf(fp, "FILE STATISTICS\n");
    fprintf(fp, "----------------------------------------\n");
    fprintf(fp, "Total bytes:        %lu\n", total_bytes);
    fprintf(fp, "Total lines:        %lu\n", total_lines);
    fprintf(fp, "Empty lines:        %lu (%.1f%%)\n", empty_lines,
            total_lines > 0 ? (100.0 * empty_lines / total_lines) : 0.0);
    fprintf(fp, "Printable lines:    %lu (%.1f%%)\n", printable_lines,
            total_lines > 0 ? (100.0 * printable_lines / total_lines) : 0.0);
    fprintf(fp, "Binary lines:       %lu (%.1f%%)\n", binary_lines,
            total_lines > 0 ? (100.0 * binary_lines / total_lines) : 0.0);
    fprintf(fp, "Uppercase lines:    %lu\n", uppercase_lines);
    fprintf(fp, "Lowercase lines:    %lu\n", lowercase_lines);
    fprintf(fp, "Numeric lines:      %lu\n", numeric_lines);
    fprintf(fp, "Mixed-case lines:   %lu\n", mixed_lines);
    fprintf(fp, "Comment lines:      %lu\n", comments_detected);
    fprintf(fp, "Long lines (>80):   %lu\n", long_lines);
    fprintf(fp, "Short lines (<20):  %lu\n", short_lines);
    fprintf(fp, "Min line length:    %lu\n", min_line_len == 0xFFFFFFFF ? 0 : min_line_len);
    fprintf(fp, "Max line length:    %lu\n", max_line_len);
    if (total_lines > 0) {
        fprintf(fp, "Avg line length:    %.1f\n", (double)total_bytes / total_lines);
    }
    fprintf(fp, "Total words:        %lu\n", words_total);
    fprintf(fp, "\n");
    
    fprintf(fp, "Line Length Distribution:\n");
    for (i = 0; i < 9; i++) {
        fprintf(fp, "  %2d-%2d chars: %lu\n", i*10, i*10+9, len_hist[i]);
    }
    fprintf(fp, "  90+ chars:   %lu\n", len_hist[9]);
    fprintf(fp, "\n");
}

void write_entropy_report(FILE *fp) {
    double entropy = compute_entropy();
    double max_entropy = 8.0;  /* 8 bits per byte */
    
    fprintf(fp, "----------------------------------------\n");
    fprintf(fp, "ENTROPY ANALYSIS\n");
    fprintf(fp, "----------------------------------------\n");
    fprintf(fp, "Shannon entropy:    %.4f bits/byte\n", entropy);
    fprintf(fp, "Maximum possible:    %.4f bits/byte\n", max_entropy);
    fprintf(fp, "Entropy ratio:      %.2f%%\n", 100.0 * entropy / max_entropy);
    
    if (entropy > 7.5) {
        fprintf(fp, "Assessment:         Highly random (possibly encrypted/compressed)\n");
    } else if (entropy > 5.0) {
        fprintf(fp, "Assessment:         Moderately structured data\n");
    } else if (entropy > 2.0) {
        fprintf(fp, "Assessment:         Low entropy, likely text or structured format\n");
    } else {
        fprintf(fp, "Assessment:         Very low entropy, highly repetitive data\n");
    }
    fprintf(fp, "\n");
}

void write_run_report(FILE *fp) {
    int i;
    
    fprintf(fp, "----------------------------------------\n");
    fprintf(fp, "RUN-LENGTH ENCODING STATISTICS\n");
    fprintf(fp, "----------------------------------------\n");
    fprintf(fp, "Total runs detected: %lu\n", total_runs);
    fprintf(fp, "Maximum run length:  %lu\n", max_run_length);
    
    if (total_runs > 0) {
        fprintf(fp, "Average run length:  %.2f\n", (double)total_bytes / total_runs);
    }
    
    /* Show most common run bytes */
    fprintf(fp, "Most frequent run-start bytes:\n");
    for (i = 0; i < 5; i++) {
        int j, top_idx = -1;
        unsigned long top_val = 0;
        for (j = 0; j < 256; j++) {
            if (run_counts[j] > top_val) {
                top_val = run_counts[j];
                top_idx = j;
            }
        }
        if (top_val == 0) break;
        fprintf(fp, "  %2d. 0x%02x (%c) - %lu runs\n", i+1, top_idx,
                (top_idx >= 32 && top_idx <= 126) ? top_idx : '.', top_val);
        run_counts[top_idx] = 0;
    }
    fprintf(fp, "\n");
}

void write_pair_report(FILE *fp) {
    int i, j;
    unsigned long max_val = 0;
    int max_i = 0, max_j = 0;
    
    for (i = 0; i < 256; i++) {
        for (j = 0; j < 256; j++) {
            if (pair_freq[i][j] > max_val) {
                max_val = pair_freq[i][j];
                max_i = i;
                max_j = j;
            }
        }
    }
    
    if (max_val > 0) {
        fprintf(fp, "----------------------------------------\n");
        fprintf(fp, "BYTE-PAIR FREQUENCY ANALYSIS\n");
        fprintf(fp, "----------------------------------------\n");
        fprintf(fp, "Most common pair: 0x%02x 0x%02x (%c%c) - %lu occurrences\n",
                max_i, max_j,
                (max_i >= 32 && max_i <= 126) ? max_i : '?',
                (max_j >= 32 && max_j <= 126) ? max_j : '?',
                max_val);
        fprintf(fp, "\n");
    }
}

void write_frequency_report(FILE *fp) {
    int i;
    unsigned long saved_freq[256];
    unsigned long max_freq = 0;
    char max_char = ' ';
    
    for (i = 0; i < 256; i++) saved_freq[i] = char_freq[i];
    
    for (i = 0; i < 256; i++) {
        if (saved_freq[i] > max_freq) {
            max_freq = saved_freq[i];
            max_char = i;
        }
    }
    
    fprintf(fp, "----------------------------------------\n");
    fprintf(fp, "BYTE FREQUENCY REPORT\n");
    fprintf(fp, "----------------------------------------\n");
    fprintf(fp, "Most frequent byte: 0x%02x (%lu occurrences, %.2f%%)\n",
            (unsigned char)max_char, max_freq,
            total_bytes > 0 ? (100.0 * max_freq / total_bytes) : 0.0);
    fprintf(fp, "\n");
    
    fprintf(fp, "Top 10 Byte Frequencies:\n");
    for (i = 0; i < 10; i++) {
        int j, top_idx = -1;
        unsigned long top_val = 0;
        for (j = 0; j < 256; j++) {
            if (saved_freq[j] > top_val) {
                top_val = saved_freq[j];
                top_idx = j;
            }
        }
        if (top_val == 0) break;
        fprintf(fp, "  %2d. 0x%02x (%c) - %lu (%.2f%%)\n", i+1, top_idx,
                (top_idx >= 32 && top_idx <= 126) ? top_idx : '.', top_val,
                total_bytes > 0 ? (100.0 * top_val / total_bytes) : 0.0);
        saved_freq[top_idx] = 0;
    }
    fprintf(fp, "\n");
}

void write_footer(FILE *fp) {
    fprintf(fp, "----------------------------------------\n");
    fprintf(fp, "INTEGRITY VERIFICATION\n");
    fprintf(fp, "----------------------------------------\n");
    fprintf(fp, "SEED: %lu\n", seed_value);
    fprintf(fp, "========================================\n");
    fprintf(fp, "END OF OUTPUT - PROCESSOR V2.1\n");
}

void write_output(void) {
    FILE *fp = fopen(OUTPUT_PATH, "w");
    if (!fp) {
        fprintf(stderr, "ERROR: Cannot write output file %s\n", OUTPUT_PATH);
        exit(1);
    }
    
    if (verbose_mode) {
        fprintf(stderr, "Writing output to: %s\n", OUTPUT_PATH);
    }
    
    write_header(fp);
    write_statistics(fp);
    write_entropy_report(fp);
    write_run_report(fp);
    write_pair_report(fp);
    write_frequency_report(fp);
    write_footer(fp);
    fclose(fp);
}

int main(int argc, char **argv) {
    init_stats();
    parse_args(argc, argv);
    
    if (read_seed() != 0) {
        fprintf(stderr, "WARNING: Using default seed 0\n");
    }
    
    if (verbose_mode) {
        fprintf(stderr, "=== Data Processor V2.1 ===\n");
        fprintf(stderr, "Processing %s ...\n", INPUT_PATH);
    } else {
        fprintf(stderr, "Processing %s ...\n", INPUT_PATH);
    }
    
    process_input();
    
    if (verbose_mode) {
        fprintf(stderr, "Writing annotated output to %s ...\n", OUTPUT_PATH);
    } else {
        fprintf(stderr, "Writing annotated output to %s ...\n", OUTPUT_PATH);
    }
    
    write_output();
    
    fprintf(stderr, "Done. Processed %lu bytes in %lu lines.\n", total_bytes, total_lines);
    
    return 0;
}
