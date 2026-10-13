#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <signal.h>
#include "config.h"
#include "crypto.h"

#define PORT 8888

static volatile int keep_running = 1;
static long total_received = 0;
static long total_dropped = 0;

typedef struct {
    char **buffer;
    int head;
    int tail;
    int size;
    pthread_mutex_t lock;
    pthread_cond_t cond;
} ring_buffer_t;

ring_buffer_t *rb;
config_t cfg;

void *worker_thread(void *arg) {
    char path[256];
    int count = 0;
    while (keep_running) {
        pthread_mutex_lock(&rb->lock);
        while (rb->head == rb->tail && keep_running) {
            pthread_cond_wait(&rb->cond, &rb->lock);
        }
        if (!keep_running && rb->head == rb->tail) {
            pthread_mutex_unlock(&rb->lock);
            break;
        }
        char *msg = rb->buffer[rb->tail];
        rb->tail = (rb->tail + 1) % rb->size;
        pthread_mutex_unlock(&rb->lock);

        snprintf(path, sizeof(path), "/var/log/aggregator/output/log_%d.txt", count++);
        FILE *f = fopen(path, "w");
        if (f) {
            if (cfg.secure_mode) {
                char sig[65];
                sign_message(msg, sig);
                fprintf(f, "%s|%s\n", msg, sig);
            } else {
                fprintf(f, "%s\n", msg);
            }
            fclose(f);
        }
        free(msg);
        // Simulate some processing overhead
        usleep(100);
    }
    return NULL;
}

void handle_sig(int sig) { keep_running = 0; }

int main() {
    signal(SIGTERM, handle_sig);
    signal(SIGINT, handle_sig);
    load_config("/app/config.yaml", &cfg);

    rb = malloc(sizeof(ring_buffer_t));
    rb->size = cfg.buffer_size;
    rb->buffer = malloc(sizeof(char *) * rb->size);
    rb->head = rb->tail = 0;
    pthread_mutex_init(&rb->lock, NULL);
    pthread_cond_init(&rb->cond, NULL);

    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in addr = { .sin_family = AF_INET, .sin_port = htons(PORT), .sin_addr.s_addr = INADDR_ANY };
    bind(sock, (struct sockaddr *)&addr, sizeof(addr));

    pthread_t worker;
    pthread_create(&worker, NULL, worker_thread, NULL);

    char buf[4096];
    while (keep_running) {
        struct sockaddr_in client_addr;
        socklen_t addr_len = sizeof(client_addr);
        int n = recvfrom(sock, buf, sizeof(buf) - 1, 0, (struct sockaddr *)&client_addr, &addr_len);
        if (n > 0) {
            buf[n] = '\0';
            total_received++;
            pthread_mutex_lock(&rb->lock);
            if ((rb->head + 1) % rb->size == rb->tail) {
                total_dropped++;
            } else {
                rb->buffer[rb->head] = strdup(buf);
                rb->head = (rb->head + 1) % rb->size;
                pthread_cond_signal(&rb->cond);
            }
            pthread_mutex_unlock(&rb->lock);
        }
    }

    pthread_cond_signal(&rb->cond);
    pthread_join(worker, NULL);
    printf("received: %ld, dropped: %ld\n", total_received, total_dropped);
    return 0;
}
