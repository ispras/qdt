#ifndef QDT_RPC_H
#define QDT_RPC_H

#include <stddef.h>
#include <stdint.h>

typedef enum {
    RPC_ERR_NO,
    RPC_ERR_READ,
    RPC_ERR_WRITE,
    RPC_ERR_ALLOC,
    RPC_ERR_UNIMPL_CALL,
    RPC_ERR_COUNT
} RPCError;

typedef void * rpc_ptr_t;

typedef rpc_ptr_t (*rpc_alloc_t)(size_t);
typedef rpc_ptr_t (*rpc_free_t)(rpc_ptr_t);

extern rpc_alloc_t rpc_alloc;
extern rpc_free_t rpc_free;

typedef rpc_ptr_t rpc_connection_t;

typedef size_t (rpc_read_t)(rpc_connection_t, rpc_ptr_t, size_t);
typedef size_t (rpc_write_t)(rpc_connection_t, rpc_ptr_t, size_t);

typedef struct RPCServer;
typedef void *RPCBackEnd;

RPCServer* rpc_server_new(rpc_connection_t, rpc_read_t, rpc_write_t,
        rpc_ptr_t ctx, RPCError*);
void rpc_server_delete(RPCServer*);

RPCBackEnd rpc_backend_new(void);
void rpc_backend_free(RPCBackEnd, RPCError*);
RPCError rpc_backend_handle_message(RPCBackEnd,
        rpc_ptr_t msg, uint32_t msg_size,
        rpc_ptr_t* response, uint32_t* response_size);

#endif QDT_RPC_H
