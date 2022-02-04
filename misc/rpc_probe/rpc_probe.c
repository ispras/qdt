#include "rpc.h"
#include "impl.h"
#include "rpc_probe.h"
#include "stdio-connection.h"

#include <stdio.h>

int main(int argc, char **argv)
{
    for (int i = 0; i < argc; i++) {
        fprintf(stderr, "argv[%d] = %s\n", i, argv[i]);
    }

    RPCProbeCtx ctx = {
        .working = true
    };

    ARRAY_ALLOC(ctx.processes);

    RPC_STDIO_CONN_STD_IN_OUT(stdioconn);

    fprintf(stderr, "main: starting RPC server\n");

    RPCServer *srv = RPC_STDIO_CONN_SERVER_NEW(stdioconn, &ctx, NULL);

    fprintf(stderr, "main: polling RPC\n");

    while (ctx.working) {
        RPCError err = rpc_server_poll(srv);
        if (err == RPC_ERR_NO) {
            fprintf(stderr, "main: ok: %s (%d)\n", rpc_error[err], err);
        } else {
            fprintf(stderr, "main: error: %s (%d)\n", rpc_error[err], err);
            break;
        }
    }

    ARRAY_FREE(ctx.processes);

    fprintf(stderr, "main: deleting RPC server\n");

    rpc_server_delete(srv);

    return 0;
}