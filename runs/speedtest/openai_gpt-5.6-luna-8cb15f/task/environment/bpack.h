#ifndef BPACK_H
#define BPACK_H
#include <stdint.h>
struct bpack_header { char magic[4]; uint8_t version, flags; uint16_t records; uint64_t base_ms; };
/* Each record is: uint16 worker, uint8 endpoint_length, int8 exit_code,
   int32 signed delta_ms, uint32 duration_ms, then endpoint bytes. */
#endif
