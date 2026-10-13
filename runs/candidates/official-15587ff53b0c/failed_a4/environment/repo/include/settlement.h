#ifndef SETTLEMENT_H
#define SETTLEMENT_H
#include <stdint.h>
typedef struct { const char *id; int64_t amount, numerator, denominator; } ledger_line;
int allocate_group(const ledger_line *, uint32_t, int64_t *);
#endif
