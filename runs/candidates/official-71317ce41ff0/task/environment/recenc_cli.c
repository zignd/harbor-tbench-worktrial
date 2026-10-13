#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sqlite3.h>
#include "librecenc/recenc.h"
#include "librecenc/types.h"

static int load_key(const char *path, recenc_key_t *key) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "Cannot open key: %s\n", path); return -1; }
    size_t n = fread(key->key, 1, RECENC_KEY_LEN, f);
    fclose(f);
    if (n != RECENC_KEY_LEN) { fprintf(stderr, "Key must be %d bytes\n", RECENC_KEY_LEN); return -1; }
    return 0;
}

static void usage(const char *prog) {
    fprintf(stderr,
        "Usage:\n"
        "  %s encrypt --db DB --key-file KEY --record-id ID --fields F1[,F2,...]\n"
        "  %s decrypt --db DB --key-file KEY --record-id ID\n",
        prog, prog);
}

static int cmd_encrypt(int argc, char **argv) {
    const char *db_path = NULL;
    const char *key_path = "/data/master.key";
    uint64_t record_id = 0;
    int record_id_set = 0;
    const char *fields_arg = NULL;
    int i;
    for (i = 0; i < argc; i++) {
        if (strcmp(argv[i], "--db") == 0 && i+1 < argc) { db_path = argv[++i]; }
        else if (strcmp(argv[i], "--key-file") == 0 && i+1 < argc) { key_path = argv[++i]; }
        else if (strcmp(argv[i], "--record-id") == 0 && i+1 < argc) {
            record_id = (uint64_t)strtoull(argv[++i], NULL, 10);
            record_id_set = 1;
        }
        else if (strcmp(argv[i], "--fields") == 0 && i+1 < argc) { fields_arg = argv[++i]; }
    }
    if (!db_path || !record_id_set || !fields_arg) {
        fprintf(stderr, "encrypt: missing --db, --record-id or --fields\n");
        return 1;
    }
    recenc_key_t key;
    if (load_key(key_path, &key) != 0) return 1;

    char *fields_copy = strdup(fields_arg);
    int num_fields = 1;
    for (char *p = fields_copy; *p; p++) if (*p == ',') num_fields++;
    char **fields = malloc(num_fields * sizeof(char*));
    size_t *field_lens = malloc(num_fields * sizeof(size_t));
    char *tok = strtok(fields_copy, ",");
    for (i = 0; i < num_fields && tok; i++) {
        fields[i] = tok;
        field_lens[i] = strlen(tok);
        tok = strtok(NULL, ",");
    }

    recenc_record_t rec;
    rec.record_id = record_id;
    rec.num_fields = num_fields;
    rec.fields = fields;
    rec.field_lens = field_lens;

    uint8_t *blob = NULL;
    size_t blob_len = 0;
    if (recenc_encrypt_record(&key, &rec, &blob, &blob_len) != 0) {
        fprintf(stderr, "Encryption failed\n");
        free(fields); free(field_lens); free(fields_copy);
        return 1;
    }

    sqlite3 *db = NULL;
    if (sqlite3_open(db_path, &db) != SQLITE_OK) {
        fprintf(stderr, "Cannot open db: %s\n", db_path);
        free(blob); free(fields); free(field_lens); free(fields_copy);
        return 1;
    }
    recenc_db_init(db);
    recenc_db_store(db, record_id, blob, blob_len);
    sqlite3_close(db);

    printf("OK record_id=%llu fields=%d bytes=%zu\n",
           (unsigned long long)record_id, num_fields, blob_len);
    free(blob); free(fields); free(field_lens); free(fields_copy);
    return 0;
}

static int cmd_decrypt(int argc, char **argv) {
    const char *db_path = NULL;
    const char *key_path = "/data/master.key";
    uint64_t record_id = 0;
    int record_id_set = 0;
    int i;
    for (i = 0; i < argc; i++) {
        if (strcmp(argv[i], "--db") == 0 && i+1 < argc) { db_path = argv[++i]; }
        else if (strcmp(argv[i], "--key-file") == 0 && i+1 < argc) { key_path = argv[++i]; }
        else if (strcmp(argv[i], "--record-id") == 0 && i+1 < argc) {
            record_id = (uint64_t)strtoull(argv[++i], NULL, 10);
            record_id_set = 1;
        }
    }
    if (!db_path || !record_id_set) {
        fprintf(stderr, "decrypt: missing --db or --record-id\n");
        return 1;
    }
    recenc_key_t key;
    if (load_key(key_path, &key) != 0) return 1;

    sqlite3 *db = NULL;
    if (sqlite3_open(db_path, &db) != SQLITE_OK) {
        fprintf(stderr, "Cannot open db: %s\n", db_path);
        return 1;
    }
    recenc_db_init(db);
    uint8_t *blob = NULL;
    size_t blob_len = 0;
    if (recenc_db_load(db, record_id, &blob, &blob_len) != 0) {
        fprintf(stderr, "Record not found: %llu\n", (unsigned long long)record_id);
        sqlite3_close(db);
        return 1;
    }
    sqlite3_close(db);

    recenc_record_t *rec = NULL;
    if (recenc_decrypt_record(&key, record_id, blob, blob_len, &rec) != 0) {
        fprintf(stderr, "Decryption failed for record_id=%llu\n", (unsigned long long)record_id);
        free(blob);
        return 1;
    }
    free(blob);
    printf("record_id=%llu num_fields=%d\n", (unsigned long long)record_id, rec->num_fields);
    for (i = 0; i < rec->num_fields; i++)
        printf("  field[%d]: len=%zu\n", i, rec->field_lens[i]);
    recenc_free_record(rec);
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 2) { usage(argv[0]); return 1; }
    if (strcmp(argv[1], "encrypt") == 0) return cmd_encrypt(argc-2, argv+2);
    if (strcmp(argv[1], "decrypt") == 0) return cmd_decrypt(argc-2, argv+2);
    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    usage(argv[0]);
    return 1;
}
