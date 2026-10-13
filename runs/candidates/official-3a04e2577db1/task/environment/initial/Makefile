CC=gcc
CFLAGS=-O2 -std=c11 -Wall -Wextra
LDLIBS=-lsqlite3
all: build/sqlgate
build/sqlgate: sqlgate.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)
clean:
	rm -f build/sqlgate
