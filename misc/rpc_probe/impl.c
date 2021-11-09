/* impl.boilerplate.c */

#include <inttypes.h>
#include "rpc.h"
#include "impl.h"
#include <stdio.h>
#include "rpc_probe.h"


RPCError TestFrontEnd_m1(void *ctx, int32_t a)
{
    fprintf(stderr, "m1: a = %" PRId32 "\n", a);
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_m2(void *ctx, int32_t a)
{
    fprintf(stderr, "m2: a = %" PRId32 "\n", a);
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_m3(void *ctx, int32_t a, int32_t b, int32_t c)
{
    fprintf(stderr, "m3: a = %" PRId32 " b = %" PRId32 " c = %" PRId32 "\n", a,
            b, c);
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_stop(void *ctx)
{
    RPCProbeCtx *pctx = (RPCProbeCtx *)ctx;
    pctx->working = false;
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_vadd(void *ctx, Point3i *ret, Point3i *a,
                           Point3i *b)
{
    ret->x = a->x + b->x;
    ret->y = a->y + b->y;
    ret->z = a->z + b->z;
    fprintf(stderr, "vadd: res = (%d, %d, %d)\n", ret->x, ret->y, ret->z);
    return RPC_ERR_NO;
}

