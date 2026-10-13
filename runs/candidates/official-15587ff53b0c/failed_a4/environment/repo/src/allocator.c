#include "settlement.h"
int allocate_group(const ledger_line *x,uint32_t n,int64_t *o){ for(uint32_t i=0;i<n;i++) o[i]=x[i].amount*x[i].numerator/x[i].denominator; return 0; }
