CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2

all: sample_unpack

sample_unpack: sample_unpack.c bpack.h
$(CC) $(CFLAGS) -o $@ sample_unpack.c

clean:
rm -f sample_unpack

.PHONY: all clean
