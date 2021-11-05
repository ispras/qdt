#include "rpc.h"

#include <stdint.h>

#include "impl.h"

#include <stdio.h>

typedef struct {
    FILE *to_client;
    FILE *from_client;
} RPCStdIOConnection;

static int rpc_read(RPCConnection conn, void *buf, long size)
{
    RPCStdIOConnection *stdioconn = (RPCStdIOConnection*) conn;

    return fread(buf, 1, size, stdioconn->from_client);
}

static int rpc_write(RPCConnection conn, void *buf, long size)
{
    RPCStdIOConnection *stdioconn = (RPCStdIOConnection*) conn;

    return fwrite(buf, 1, size, stdioconn->to_client);
}

int main(int argc, char *argv)
{
    RPCStdIOConnection stdioconn = {
            .to_client = stdout,
            .from_client = stdin
    };

    RPCServer *srv = rpc_server_new((RPCConnection) &stdioconn, rpc_read,
            rpc_write, NULL);

    rpc_server_delete(srv);

    return 0;
}

void TestFrontEnd_cross(void *ctx, Point3i *ret, Point3i *a, Point3i *b)
{
    fprintf(stderr, "cross\n", a);
}

void TestFrontEnd_m1(void *ctx, int32_t a)
{
    fprintf(stderr, "m1: a = %" PRId32 "\n", a);
}

void TestFrontEnd_m2(void *ctx, int32_t a)
{
    fprintf(stderr, "m2: a = %" PRId32 "\n", a);
}

void TestFrontEnd_m3(void *ctx, int32_t a, int32_t b, int32_t c)
{
    fprintf(stderr, "m3: a = %" PRId32 " b = %" PRId32 " c = %" PRId32 "\n", a,
            b, c);
}
