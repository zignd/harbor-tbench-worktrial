CC      = gcc
CFLAGS  = -Wall -Wextra -O2 -fPIC -I.
LDFLAGS = -lssl -lcrypto -lsqlite3

SRCS = nonce.c counter.c serialize.c mac.c encrypt.c db.c
OBJS = $(SRCS:.c=.o)

.PHONY: all clean

all: librecenc.so

librecenc.so: $(OBJS)
	$(CC) -shared -o $@ $(OBJS) $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) librecenc.so
