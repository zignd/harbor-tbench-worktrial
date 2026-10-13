/*
 * main.c - TCP server loop for the WAL audit service.
 * Listens on port 7741, accepts connections, dispatches to protocol handler.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <signal.h>
#include "logaudit.h"

#define LISTEN_PORT   7741
#define BACKLOG       32
#define MAX_LINE      (131072 + 4)

static volatile int g_running = 1;

static void handle_sigterm(int sig) {
    (void)sig;
    g_running = 0;
}

static int create_listen_socket(int port) {
    int fd;
    struct sockaddr_in addr;
    int opt = 1;

    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        perror("socket");
        return -1;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        perror("setsockopt");
        close(fd);
        return -1;
    }
    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons((uint16_t)port);
    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(fd);
        return -1;
    }
    if (listen(fd, BACKLOG) < 0) {
        perror("listen");
        close(fd);
        return -1;
    }
    return fd;
}

static void handle_client(int client_fd, AuditContext *ctx) {
    FILE *in  = fdopen(dup(client_fd), "r");
    FILE *out = fdopen(dup(client_fd), "w");
    char line[MAX_LINE];

    if (!in || !out) {
        if (in)  fclose(in);
        if (out) fclose(out);
        return;
    }

    while (fgets(line, sizeof(line), in)) {
        size_t len = strlen(line);
        if (len > 0 && line[len-1] == '\n') {
            line[len-1] = '\0';
            len--;
        }
        if (len == 0) continue;
        protocol_handle_line(ctx, line, len, out);
        fflush(out);
    }
    fclose(in);
    fclose(out);
}

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;

    signal(SIGTERM, handle_sigterm);
    signal(SIGPIPE, SIG_IGN);

    AuditContext *ctx = audit_context_create();
    if (!ctx) {
        fprintf(stderr, "Failed to create audit context\n");
        return 1;
    }

    int lfd = create_listen_socket(LISTEN_PORT);
    if (lfd < 0) {
        audit_context_destroy(ctx);
        return 1;
    }

    fprintf(stdout, "logaudit listening on port %d\n", LISTEN_PORT);
    fflush(stdout);

    while (g_running) {
        struct sockaddr_in client_addr;
        socklen_t clen = sizeof(client_addr);
        int cfd = accept(lfd, (struct sockaddr *)&client_addr, &clen);
        if (cfd < 0) {
            if (errno == EINTR) continue;
            perror("accept");
            break;
        }
        /* Reset per-session state */
        audit_context_reset_session(ctx);
        handle_client(cfd, ctx);
        close(cfd);
    }

    close(lfd);
    audit_context_destroy(ctx);
    return 0;
}
