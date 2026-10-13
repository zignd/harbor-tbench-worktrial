#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <time.h>

#define DEST_PORT 9999

struct data_packet {
    uint32_t id;
    int64_t timestamp_ns;
    double values[3];
    uint32_t crc;
} __attribute__((packed));

struct heartbeat_packet {
    uint32_t id;
    int64_t timestamp_ns;
} __attribute__((packed));

int main(int argc, char *argv[]) {
    int sockfd;
    struct sockaddr_in servaddr;
    if ((sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) exit(1);
    memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;
    servaddr.sin_port = htons(DEST_PORT);
    servaddr.sin_addr.s_addr = inet_addr("127.0.0.1");

    int count = (argc > 1) ? atoi(argv[1]) : 100000;
    struct timespec ts;

    for (int i = 0; i < count; i++) {
        clock_gettime(CLOCK_REALTIME, &ts);
        uint64_t ns = (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;

        if (i % 500 == 0) {
            struct heartbeat_packet hb = { (uint32_t)i, (int64_t)ns };
            sendto(sockfd, &hb, sizeof(hb), 0, (const struct sockaddr *)&servaddr, sizeof(servaddr));
        } else {
            struct data_packet dp = { (uint32_t)i, (int64_t)ns, { (double)i, (double)i*1.1, (double)i*1.2 }, 0xdeadbeef };
            sendto(sockfd, &dp, sizeof(dp), 0, (const struct sockaddr *)&servaddr, sizeof(servaddr));
        }
        if (i % 100 == 0) usleep(1);
    }
    close(sockfd);
    return 0;
}
