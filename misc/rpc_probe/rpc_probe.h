#ifndef RPC_PROBE_H
#define RPC_PROBE_H

#include "array.h"
#include <stdbool.h>

typedef struct {
    int pid;
    int fd_out;
    int fd_err;
} RPCProcess;

typedef struct {
    bool working;

    ARRAY_DECL(RPCProcess, processes);

    char iobuf[4096];
} RPCProbeCtx;

#endif /* RPC_PROBE_H */
