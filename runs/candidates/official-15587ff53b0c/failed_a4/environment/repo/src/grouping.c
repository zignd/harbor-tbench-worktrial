#include "settlement.h"
unsigned group_hash(const char *s){ unsigned h=2166136261u; while(s&&*s) h=(h^*(unsigned char)s++)*16777619u; return h; }
