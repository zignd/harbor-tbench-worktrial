.PHONY: test release clean
bin/reconcile-pack: src/main.c
mkdir -p bin; gcc -O2 -Iinclude src/main.c -o bin/reconcile-pack
test: bin/reconcile-pack
./tests/smoke.sh
release: bin/reconcile-pack
mkdir -p dist
sha256sum bin/reconcile-pack | awk '{print "reconcile-pack " $$1}' > dist/MANIFEST
tar -czf dist/reconcile-pack.tar.gz bin/reconcile-pack dist/MANIFEST
clean:
rm -rf bin dist
