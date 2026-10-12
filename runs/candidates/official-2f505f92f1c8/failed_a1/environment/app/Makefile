# Makefile for the WAL audit service

CC      = gcc
CFLAGS  = -Wall -Wextra -O2 -std=c11 -D_POSIX_C_SOURCE=200809L -I/app/src
LDFLAGS = -lssl -lcrypto -lsqlite3

SRCDIR  = /app/src
BINDIR  = /app/bin

SOURCES = $(SRCDIR)/main.c \
          $(SRCDIR)/protocol.c \
          $(SRCDIR)/wal_record.c \
          $(SRCDIR)/refund_resolver.c \
          $(SRCDIR)/util.c \
          $(SRCDIR)/metrics.c \
          $(SRCDIR)/config.c

OBJECTS = $(SOURCES:.c=.o)

TARGET  = $(BINDIR)/logaudit

.PHONY: all clean

all: $(BINDIR) $(TARGET)

$(BINDIR):
	mkdir -p $(BINDIR)

$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(SRCDIR)/%.o: $(SRCDIR)/%.c $(SRCDIR)/logaudit.h
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJECTS) $(TARGET)
