.PHONY: test release clean
.RECIPEPREFIX := >
CC=gcc
SRC=src/parser.c src/rational.c src/grouping.c src/allocator.c
build/components: $(SRC) src/cli.c
>mkdir -p build
>$(CC) -std=c11 -Wall -Wextra -Iinclude $(SRC) src/cli.c -o $@
test: build/components
>@test -x tools/reconcile-pack
>python3 tests/smoke.py
release: test
>rm -rf stage dist && mkdir -p stage/bin stage/docs dist
>cp tools/reconcile-pack stage/bin/reconcile-pack && chmod 755 stage/bin/reconcile-pack
>cp docs/format.md stage/docs/format.md
>printf '%s\n' bin/reconcile-pack docs/format.md > stage/MANIFEST
>cp stage/MANIFEST dist/MANIFEST
>SOURCE_DATE_EPOCH=0 tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner -czf dist/reconcile-pack.tar.gz -C stage bin docs MANIFEST
clean:
>rm -rf build stage dist
