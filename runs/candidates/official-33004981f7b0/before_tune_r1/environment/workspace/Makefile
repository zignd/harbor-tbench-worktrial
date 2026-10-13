CC=gcc
CFLAGS=-O2 -std=c11 -Wall -Wextra

all: reconcile settle-crypto

reconcile: reconcile.c
	$(CC) $(CFLAGS) -o $@ $<

settle-crypto: helper.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f reconcile settle-crypto
