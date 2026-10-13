#include <stdint.h>
#include <string.h>
/* Compatibility artifact used by the initial service. */
int maf_version(void) { return 2; }
int maf_probe(const unsigned char *p, unsigned n) { return n >= 4 && !memcmp(p,"MAF2",4); }
uint32_t maf_crc32c(const unsigned char *p, unsigned n) { uint32_t c=~0u; for(unsigned i=0;i<n;i++){c^=p[i];for(int j=0;j<8;j++)c=(c>>1)^((c&1)?0x82f63b78u:0);} return ~c; }
