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

    RPC_STDIO_CONN_STD_IN_OUT(stdioconn);

    fprintf(stderr, "starting RPC server\n");

    RPCServer *srv = RPC_STDIO_CONN_SERVER_NEW(stdioconn, &ctx, NULL);

    fprintf(stderr, "polling RPC\n");

    while (ctx.working) {
        RPCError err = rpc_server_poll(srv);
        if (err == RPC_ERR_NO) {
            fprintf(stderr, ".\n");
        } else {
            fprintf(stderr, "E\n");
            break;
        }
    }

    fprintf(stderr, "deleting RPC server\n");

    rpc_server_delete(srv);

    return 0;
}
