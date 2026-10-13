#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sqlite3.h>
#include <openssl/evp.h>
#include "librecenc/recenc.h"
#include "librecenc/types.h"

/* SHA-256 of decrypted record stream, used to verify reproduction */
static const char PAPER_HASH[] =
    "5c7bd1969f25498a62b292300b5246126c3f3d1c8851bd910b093224f19264e3";

static int load_key(const char *path, recenc_key_t *key) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "Cannot open key: %s\n", path); return -1; }
    size_t n = fread(key->key, 1, RECENC_KEY_LEN, f);
    fclose(f);
    return (n == RECENC_KEY_LEN) ? 0 : -1;
}

static void hash_record(EVP_MD_CTX *ctx, uint64_t rid, recenc_record_t *rec) {
    uint8_t tmp[8];
    tmp[0]=(rid>>0)&0xFF; tmp[1]=(rid>>8)&0xFF;
    tmp[2]=(rid>>16)&0xFF; tmp[3]=(rid>>24)&0xFF;
    tmp[4]=(rid>>32)&0xFF; tmp[5]=(rid>>40)&0xFF;
    tmp[6]=(rid>>48)&0xFF; tmp[7]=(rid>>56)&0xFF;
    EVP_DigestUpdate(ctx, tmp, 8);
    uint32_t nf = (uint32_t)rec->num_fields;
    tmp[0]=nf&0xFF; tmp[1]=(nf>>8)&0xFF;
    tmp[2]=(nf>>16)&0xFF; tmp[3]=(nf>>24)&0xFF;
    EVP_DigestUpdate(ctx, tmp, 4);
    int fi;
    for (fi = 0; fi < rec->num_fields; fi++) {
        uint32_t flen = (uint32_t)rec->field_lens[fi];
        tmp[0]=flen&0xFF; tmp[1]=(flen>>8)&0xFF;
        tmp[2]=(flen>>16)&0xFF; tmp[3]=(flen>>24)&0xFF;
        EVP_DigestUpdate(ctx, tmp, 4);
        EVP_DigestUpdate(ctx, (uint8_t*)rec->fields[fi], rec->field_lens[fi]);
    }
}

int main(int argc, char **argv) {
    const char *db_path = "/data/experiment.db";
    const char *key_path = "/data/master.key";
    int i;
    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--db") == 0 && i+1 < argc) db_path = argv[++i];
        else if (strcmp(argv[i], "--key-file") == 0 && i+1 < argc) key_path = argv[++i];
    }

    recenc_key_t key;
    if (load_key(key_path, &key) != 0) {
        fprintf(stderr, "Failed to load key from %s\n", key_path);
        return 1;
    }

    sqlite3 *db;
    if (sqlite3_open(db_path, &db) != SQLITE_OK) {
        fprintf(stderr, "Cannot open database: %s\n", db_path);
        return 1;
    }

    /* Check 12 regression records */
    int reg_pass = 0;
    uint64_t reg_ids[] = {9001,9002,9003,9004,9005,9006,9007,9008,9009,9010,9011,9012};
    for (i = 0; i < 12; i++) {
        uint8_t *blob = NULL; size_t blen = 0;
        if (recenc_db_load(db, reg_ids[i], &blob, &blen) == 0) {
            recenc_record_t *rec = NULL;
            if (recenc_decrypt_record(&key, reg_ids[i], blob, blen, &rec) == 0) {
                reg_pass++;
                recenc_free_record(rec);
            }
            free(blob);
        }
    }
    printf("Record integrity: %s (%d/12 known records)\n",
           reg_pass == 12 ? "PASS" : "FAIL", reg_pass);

    /* Decrypt all records and compute hash */
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha256(), NULL);

    sqlite3_stmt *stmt;
    sqlite3_prepare_v2(db,
        "SELECT record_id, blob FROM encrypted_records ORDER BY record_id",
        -1, &stmt, NULL);

    int total = 0, failed = 0;
    uint64_t first_mismatch = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        uint64_t rid = (uint64_t)sqlite3_column_int64(stmt, 0);
        int blen = sqlite3_column_bytes(stmt, 1);
        const uint8_t *bdata = sqlite3_column_blob(stmt, 1);
        uint8_t *blob = malloc(blen);
        memcpy(blob, bdata, blen);

        recenc_record_t *rec = NULL;
        if (recenc_decrypt_record(&key, rid, blob, blen, &rec) != 0) {
            if (first_mismatch == 0) first_mismatch = rid;
            failed++;
            free(blob);
            /* feed zeros to keep hash deterministic position */
            uint8_t zero[12] = {0};
            EVP_DigestUpdate(ctx, zero, 12);
            continue;
        }
        free(blob);
        hash_record(ctx, rid, rec);
        recenc_free_record(rec);
        total++;
    }
    sqlite3_finalize(stmt);
    sqlite3_close(db);

    uint8_t digest[32];
    unsigned int dlen = 32;
    EVP_DigestFinal_ex(ctx, digest, &dlen);
    EVP_MD_CTX_free(ctx);

    char hex[65];
    for (i = 0; i < 32; i++) sprintf(hex + 2*i, "%02x", digest[i]);
    hex[64] = '\0';

    int match = (strcmp(hex, PAPER_HASH) == 0);
    printf("Reproduction check: %s\n", match ? "PASS" : "FAIL");
    if (!match) {
        printf("  paper_hash:    %.8s...%s\n", PAPER_HASH, PAPER_HASH + 56);
        printf("  computed_hash: %.8s...%s\n", hex, hex + 56);
        if (first_mismatch)
            printf("  first mismatch: record_id=%llu\n", (unsigned long long)first_mismatch);
    }
    return match ? 0 : 1;
}
