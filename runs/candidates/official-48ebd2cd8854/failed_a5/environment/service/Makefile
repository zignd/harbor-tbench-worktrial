CC      = gcc
CFLAGS  = -Wall -Wextra -O2 -g
LDFLAGS = -lsqlite3

SRCS = main.c config_parser.c db_fetch.c aggregator.c db_writer.c
OBJS = $(SRCS:.c=.o)
TARGET = aggregator

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) $(TARGET)

main.o: main.c config_parser.h db_fetch.h aggregator.h db_writer.h
config_parser.o: config_parser.c config_parser.h
db_fetch.o: db_fetch.c db_fetch.h
aggregator.o: aggregator.c aggregator.h db_fetch.h config_parser.h
db_writer.o: db_writer.c db_writer.h db_fetch.h config_parser.h aggregator.h
