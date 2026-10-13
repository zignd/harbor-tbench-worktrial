.RECIPEPREFIX := >
CC ?= gcc
CFLAGS ?= -std=c17 -Wall -Wextra -Werror -pedantic

.PHONY: all clean check

all: unpack_sample

unpack_sample: test_unpack.c
>$(CC) $(CFLAGS) -o $@ test_unpack.c

check: unpack_sample
>@set -e; for pack in /var/log/telemetry/backend/*.bpack; do ./unpack_sample "$$pack"; done | head -n 3

clean:
>rm -f unpack_sample
