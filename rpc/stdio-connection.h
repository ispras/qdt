#ifndef QDT_RPC_STDIO_CONNECTION_H
#define QDT_RPC_STDIO_CONNECTION_H

#include <stdio.h>

typedef struct {
    FILE *to_client;
    FILE *from_client;
} RPCStdIOConnection;

static inline size_t rpc_stdio_connection_read(rpc_connection_t conn,
                                               void *buf,
                                               size_t size)
{
    RPCStdIOConnection *stdioconn = (RPCStdIOConnection*) conn;

    return fread(buf, 1, size, stdioconn->from_client);
}

static inline size_t rpc_stdio_connection_write(rpc_connection_t conn,
                                                void *buf,
                                                size_t size)
{
    RPCStdIOConnection *stdioconn = (RPCStdIOConnection*) conn;

    size_t ret = fwrite(buf, 1, size, stdioconn->to_client);

    if (ret) {
        fflush(stdioconn->to_client);
    }

    return ret;
}

#define RPC_STDIO_CONN_STD_IN_OUT(CONN_NAME) \
    RPCStdIOConnection CONN_NAME = { \
        .to_client = stdout, \
        .from_client = stdin, \
    }

#define RPC_STDIO_CONN_ARGS(CONN_NAME) \
    (rpc_connection_t) &(CONN_NAME), \
    rpc_stdio_connection_read, \
    rpc_stdio_connection_write

#define RPC_STDIO_CONN_SERVER_NEW(CONN_NAME, CTX, ERR_PTR) \
    rpc_server_new(RPC_STDIO_CONN_ARGS(CONN_NAME), CTX, ERR_PTR)

#endif /* QDT_RPC_STDIO_CONNECTION_H */
