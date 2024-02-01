/* impl.boilerplate.c */

#include <inttypes.h>
#include "rpc.h"
#include "impl.h"
#include <stdio.h>
#include <string.h>
#include "rpc_probe.h"
#include <stdbool.h>
#include <malloc.h>
#include <stdlib.h>
#include <unistd.h> /* execve, pipe, dup2, close */

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

int count_strings(const RPCBuffer *b)
{
    int n = 0;
    const uint8_t *p = b->data;
    const uint8_t *end = p + b->size;
    while (p < end) {
        n++;
        p += strlen(p) + 1;
    }
    return n;
}

int string_chain2string_array(const RPCBuffer *b, char ***arr)
{
    int n = count_strings(b);
    *arr = (char **)malloc(sizeof(char *) * (n + 1));
    const uint8_t *p = b->data;
    const uint8_t *end = p + b->size;
    char **ap = *arr;
    while (p < end) {
        int l = strlen(p) + 1;
        *ap = malloc(l);
        memcpy(*ap, p, l);
        ap++;
        p += l;
    }
    *ap = NULL;
    return n;
}

#define FOREACH_STRING(VAR, ARRAY, CODE) do { \
    char **VAR = ARRAY; \
    while (*VAR != NULL) { \
        CODE \
        VAR++; \
    } \
} while ((0))

int string_array_len(char **a)
{
    int l = 0;
    while (*a != NULL) {
        l++;
        a++;
    }
    return l;
}

char** string_array_join(char **a, char **b)
{
    int al = string_array_len(a), bl = string_array_len(b);
    char **res = (char **) malloc(sizeof(char *) * (al + bl + 1));
    char **rp = res, **ap = a, **bp = b;
    int i;
    for (i = 0; i < al; i++, ap++, rp++) {
        int l = strlen(*ap);
        *rp = malloc(l + 1);
        memcpy(*rp, *ap, l + 1);
    }
    for (i = 0; i < bl; i++, bp++, rp++) {
        int l = strlen(*bp);
        *rp = malloc(l + 1);
        memcpy(*rp, *bp, l + 1);
    }
    *rp = NULL;
    return res;
}

void string_array_free(char **arr)
{
    char **ap = arr;
    while (*ap != NULL) {
        free(*ap);
        ap++;
    }
    free(arr);
}

/* TODO: implement for Windows */
RPCError TestFrontEnd_execve(RPCBackEnd be, rpc_ptr_t ctx, int32_t *ret,
                             RPCString *filename, RPCBuffer *argv,
                             RPCBuffer *envp)
{
    fprintf(stderr, "impl: execve: %s\n", filename->data);

    fprintf(stderr, "impl: count_strings(argv) = %d\n",
            count_strings(argv));
    fprintf(stderr, "impl: count_strings(envp) = %d\n",
            count_strings(envp));

    int out_link[2], err_link[2];
    pid_t pid;

    /* TODO: error checking & cleanup */

    pipe(out_link);
    pipe(err_link);

    pid = fork();
    if (pid == 0) {
        /* child */
        char **argv_arr, **envp_arr;
        string_chain2string_array(argv, &argv_arr);
        string_chain2string_array(envp, &envp_arr);

        char *arg0[] = {
            filename->data,
            NULL
        };

        char **full_argv_arr = string_array_join(arg0, argv_arr);
        string_array_free(argv_arr);

        int i;

        i = 0;
        FOREACH_STRING(p, full_argv_arr,
            fprintf(stderr, "impl: argv[%d] = %s\n", i, *p);
            i++;
        );

        i = 0;
        FOREACH_STRING(p, envp_arr,
            fprintf(stderr, "impl: envp[%d] = %s\n", i, *p);
            i++;
        );

        dup2(out_link[1], STDOUT_FILENO);
        close(out_link[0]);
        dup2(err_link[1], STDERR_FILENO);
        close(err_link[0]);

        execve(filename->data, full_argv_arr, envp_arr);

        string_array_free(full_argv_arr );
        string_array_free(envp_arr);

        exit(0);
    } else {
        /* parent */
        close(out_link[1]);
        close(err_link[1]);

        RPCProcess *p;

        RPCProbeCtx *probe_ctx = (RPCProbeCtx *)ctx;
        ARRAY_ALLOC_EL(probe_ctx->processes, p);
        p->pid = pid;
        p->fd_out = out_link[0];
        p->fd_err = err_link[0];

        *ret = ARRAY_INDEX(probe_ctx->processes, p);
    }

    return RPC_ERR_NO;
}

RPCError TestFrontEnd_read_err(RPCBackEnd be, rpc_ptr_t ctx, RPCBuffer *ret,
                               int32_t pid)
{
    /* TODO: error checking */
    RPCProbeCtx *probe_ctx = (RPCProbeCtx *)ctx;
    RPCProcess *p = &probe_ctx->processes[pid];
    ret->data = probe_ctx->iobuf;
    ret->size = read(p->fd_err, probe_ctx->iobuf, sizeof(probe_ctx->iobuf));

    return RPC_ERR_NO;
}

RPCError TestFrontEnd_read_out(RPCBackEnd be, rpc_ptr_t ctx, RPCBuffer *ret,
                               int32_t pid)
{
    /* TODO: error checking */
    RPCProbeCtx *probe_ctx = (RPCProbeCtx *)ctx;
    RPCProcess *p = &probe_ctx->processes[pid];
    ret->data = probe_ctx->iobuf;
    ret->size = read(p->fd_out, probe_ctx->iobuf, sizeof(probe_ctx->iobuf));

    return RPC_ERR_NO;
}
