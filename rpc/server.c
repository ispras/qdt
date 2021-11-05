#include "rpc.h"
#include "backend.h"

#include <malloc.h>

rpc_alloc_t rpc_alloc = malloc;
rpc_free_t rpc_free = free;

typedef struct {
    rpc_connection_t conn;
    rpc_ptr_t buf;
    size_t allocated;
    rpc_read_t read_func;
    rpc_write_t write_func;
    rpc_ptr_t ctx;
    RPCBackEnd be;
} RPCServer;

RPCServer* rpc_server_new(rpc_connection_t conn, rpc_read_t read_func,
        rpc_write_t write_func, rpc_ptr_t ctx, RPCError *err)
{
    RPCServer *s = rpc_alloc(sizeof(RPCServer));
    if (s == NULL) {
        if (err != NULL) *err = RPC_ERR_ALLOC;
        return NULL;
    }
    s->allocated = 1 << 20;
    s->buf = rpc_alloc(s->allocated);
    if (s->buf == NULL) {
        rpc_free(s);
        if (err != NULL) *err = RPC_ERR_ALLOC;
        return NULL;
    }

    s->be = rpc_backend_new(err);
    if (s->be == NULL) {
        rpc_free(s->buf);
        rpc_free(s);
        return NULL;
    }

    s->conn = conn;
    s->read_func = read_func;
    s->write_func = write_func;
    s->ctx = ctx;

    return s;
}

void rpc_server_delete(RPCServer* s)
{
    rpc_free(s->buf);
    rpc_free(s);
}

RPCError rpc_server_poll(RPCServer* s)
{
    size_t need, ret;
    uint8_t *p;

    p = s->buf
    need = 4;

    while (need) {
        ret = s->read_func(s->conn, p, need);
        if (!ret) {
            return RPC_ERR_READ;
        }
        p += ret;
        need -= ret;
    }

    uint32_t msg_len = *(uint32_t*) s->buf;

    if (s->allocated < msg_len) {
        rpc_ptr_t new_buf = rpc_alloc(msg_len);
        if (new_buf == NULL) {
            return RPC_ERR_ALLOC;
        }
        rpc_free(s->buf);
        s->buf = new_buf;
    }

    need = msg_len;
    p = s->buf;

    while (need) {
        ret = s->read_func(s->conn, p, need);
        if (!ret) {
            return RPC_ERR_READ;
        }
        p += ret;
        need -= ret;
    }

    uint8_t *response;
    uint32_t response_size;
    RPCError be_err = rpc_backend_handle_message(s->be, s->buf, msg_len,
            &response, &response_size);

    if (be_err != RPC_ERR_NO) {
        return be_err;
    }

    uint8_t size_buf[4];
    *(uint32_t*)size_buf = response_size;

    need = 4;
    p = size_buf;

    while (need) {
        ret = s->write_func(s->conn, p, need);
        if (!ret) {
            return RPC_ERR_WRITE;
        }
        p += ret;
        need -= ret;
    }

    p = response;
    need = response_size;

    while (need) {
        ret = s->write_func(s->conn, p, need);
        if (!ret) {
            return RPC_ERR_WRITE;
        }
        p += ret;
        need -= ret;
    }

    return RPC_ERR_NO;
}
