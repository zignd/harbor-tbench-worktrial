#include <stdio.h>
#include <stdlib.h>
#include <math.h>

// Use long double for internal calculations to simulate high precision requirements
long double calculate(long double duration, long double intensity) {
    if (duration < 0 || intensity < 0) return 0.0;
    
    long double base_rate = 12.55;
    long double fee = duration * intensity * base_rate;
    
    // Tiered pricing logic
    if (intensity > 0.8500000000000001L) {
        fee *= 1.15L;
    }
    
    if (intensity * duration > 100.0L) {
        fee += 5.25L;
    }

    // Extremely specific threshold mentioned in blueprint
    if (intensity >= 0.999999L) {
        fee += 10.0L;
    }

    return fee;
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <duration> <intensity>\n", argv[0]);
        return 1;
    }

    char *endptr1, *endptr2;
    long double duration = strtold(argv[1], &endptr1);
    long double intensity = strtold(argv[2], &endptr2);

    if (*endptr1 != '\0' || *endptr2 != '\0') {
        // Handle non-numeric or malformed input like a finicky tool
        printf("NaN\n");
        return 0;
    }

    long double result = calculate(duration, intensity);
    // Output with high precision to ensure SQLite standard ROUND fails
    printf("%.15Lf\n", result);

    return 0;
}
