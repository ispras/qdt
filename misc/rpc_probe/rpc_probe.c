#include "rpc.h"
#include "impl.h"
#include "rpc_probe.h"

#include <stdio.h>

typedef struct {
    FILE *to_client;
    FILE *from_client;
} RPCStdIOConnection;

static size_t rpc_read(rpc_connection_t conn, void *buf, size_t size)
{
    RPCStdIOConnection *stdioconn = (RPCStdIOConnection*) conn;

    return fread(buf, 1, size, stdioconn->from_client);
}

static size_t rpc_write(rpc_connection_t conn, void *buf, size_t size)
{
    RPCStdIOConnection *stdioconn = (RPCStdIOConnection*) conn;

    size_t ret = fwrite(buf, 1, size, stdioconn->to_client);

    if (ret) fflush(stdioconn->to_client);

    return ret;
}

int main(int argc, char **argv)
{
    for (int i = 0; i < argc; i++) {
        fprintf(stderr, "argv[%d] = %s\n", i, argv[i]);
    }

    RPCStdIOConnection stdioconn = {
            .to_client = stdout,
            .from_client = stdin
    };

    RPCProbeCtx ctx = {
        .working = true
    };

    fprintf(stderr, "starting RPC server\n");

    RPCServer *srv = rpc_server_new((rpc_connection_t) &stdioconn, rpc_read,
            rpc_write, &ctx, NULL);

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
