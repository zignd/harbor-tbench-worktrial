all: lib/libmafcodec.so
lib/libmafcodec.so: libmafcodec.c
mkdir -p lib
gcc -shared -fPIC -O2 -o $@ $<
clean:
rm -f lib/libmafcodec.so

stream-inspect: stream-inspect.c
gcc -Wall -Wextra -O2 -o $@ $<
