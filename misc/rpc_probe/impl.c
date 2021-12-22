/* impl.boilerplate.c */

#include <inttypes.h>
#include "rpc.h"
#include "impl.h"
#include <stdio.h>
#include <string.h>
#include "rpc_probe.h"
#include <stdbool.h>

#define MIN(A, B) (((B) > (A)) ? (B) : (A))

RPCError TestFrontEnd_bufcmp(RPCBackEnd be, rpc_ptr_t ctx, int8_t *ret,
                             BufCmpTask *t)
{
    fprintf(stderr, "impl: bufcmp: %d, %d:", t->a.size, t->b.size);
    fflush(stderr);
    uint16_t min_size = MIN(t->a.size, t->b.size);

    fprintf(stderr, " %c, %c:", t->a.data[0], t->b.data[0]);

    *ret = memcmp(t->a.data, t->b.data, min_size);

    bool by_size = false;
    if (!*ret) {
        if (t->a.size > t->b.size) {
            *ret = 1;
            by_size = true;
        } else if (t->a.size < t->b.size) {
            *ret = -1;
            by_size = true;
        }
    }

    fprintf(stderr, " %d", (int)*ret);

    if (by_size) {
        fprintf(stderr, " (by size)\n");
    } else {
        fprintf(stderr, "\n");
    }

    return RPC_ERR_NO;
}

RPCError TestFrontEnd_m1(RPCBackEnd be, rpc_ptr_t ctx, int32_t a)
{
    fprintf(stderr, "impl: m1: a = %" PRId32 "\n", a);
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_m2(RPCBackEnd be, rpc_ptr_t ctx, int32_t a)
{
    fprintf(stderr, "impl: m2: a = %" PRId32 "\n", a);
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_m3(RPCBackEnd be, rpc_ptr_t ctx, int32_t a, int32_t b,
                         int32_t c)
{
    fprintf(stderr,
            "impl: m3: a = %" PRId32 " b = %" PRId32 " c = %" PRId32 "\n", a,
            b, c);
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_p(RPCBackEnd be, rpc_ptr_t ctx, RPCString *s)
{
    fprintf(stderr, "impl: p:");
    fflush(stderr);
    fprintf(stderr, " \"%s\"\n", s->data);
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_stop(RPCBackEnd be, rpc_ptr_t ctx)
{
    RPCProbeCtx *pctx = (RPCProbeCtx *)ctx;
    pctx->working = false;
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_strcmp(RPCBackEnd be, rpc_ptr_t ctx, int8_t *ret,
                             RPCString *a, RPCString *b)
{
    fprintf(stderr, "impl: strcmp:");
    fflush(stderr);
    *ret = strcmp(a->data, b->data);
    fprintf(stderr, " \"%s\" \"%s\" = %d\n", a->data, b->data,
            (int)*ret);
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_vadd(RPCBackEnd be, rpc_ptr_t ctx, Point3i *ret,
                           Point3i *a, Point3i *b)
{
    ret->x = a->x + b->x;
    ret->y = a->y + b->y;
    ret->z = a->z + b->z;
    fprintf(stderr, "impl: add: res = (%d, %d, %d)\n", ret->x, ret->y, ret->z);
    return RPC_ERR_NO;
}

#define VERSION_STRING "rpc_probe v0.2"

RPCError TestFrontEnd_version_info(RPCBackEnd be, rpc_ptr_t ctx,
                                   VersionInfo *ret)
{
    fprintf(stderr, "impl: version_info\n");
    ret->version_string.size = strlen(VERSION_STRING);
    ret->version_string.data = VERSION_STRING;
    ret->version_code = 0x02;
    return RPC_ERR_NO;
}

RPCError TestFrontEnd_version_string(RPCBackEnd be, rpc_ptr_t ctx,
                                     RPCString *ret)
{
    fprintf(stderr, "impl: version_string\n");
    ret->length = strlen(VERSION_STRING);
    ret->data = VERSION_STRING;
    return RPC_ERR_NO;
}

