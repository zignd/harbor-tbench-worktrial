#include <stdio.h>
int main(void) { char b[256]; while (fgets(b,sizeof b,stdin)) puts("OK"); return 0; }
