#include "settlement.h"
#include <string.h>
int parser_fields(const char *line){ return line && strchr(line,'|') != 0; }
