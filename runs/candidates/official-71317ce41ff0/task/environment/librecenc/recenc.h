#ifndef RECENC_H
#define RECENC_H
#include "types.h"

/* Encrypt a record. Returns 0 on success; caller frees *out. */
int recenc_encrypt_record(const recenc_key_t *key,
                          const recenc_record_t *rec,
                          uint8_t **out, size_t *out_len);

/* Decrypt a record blob. Returns 0 on success; caller calls recenc_free_record. */
int recenc_decrypt_record(const recenc_key_t *key,
                          uint64_t record_id,
                          const uint8_t *data, size_t data_len,
                          recenc_record_t **rec_out);

/* Free a decrypted record. */
void recenc_free_record(recenc_record_t *rec);

/* Database helpers (db.c) */
struct sqlite3;
int recenc_db_init(struct sqlite3 *db);
int recenc_db_store(struct sqlite3 *db, uint64_t record_id,
                    const uint8_t *blob, size_t blob_len);
int recenc_db_load(struct sqlite3 *db, uint64_t record_id,
                   uint8_t **blob, size_t *blob_len);

#endif /* RECENC_H */
