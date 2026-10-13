#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    if (argc != 3) return 1;
    long double duration = strtold(argv[1], NULL);
    long double intensity = strtold(argv[2], NULL);
    long double rate = 10.5L;
    if (intensity > 0.999999L) {
        rate = 15.75L;
    } else if (intensity > 0.8500001L) {
        rate = 12.25L;
    }
    long double amount = duration * intensity * rate;
    if (duration * intensity > 100.0L) {
        amount *= 1.05L;
    }
    printf("%.18Lf\n", amount);
    return 0;
}
