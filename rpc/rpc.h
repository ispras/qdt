#ifndef QDT_RPC_RPC_H
#define QDT_RPC_RPC_H

#include <stddef.h>
#include <stdint.h>

typedef enum {
    RPC_ERR_NO,
    RPC_ERR_READ,
    RPC_ERR_WRITE,
    RPC_ERR_ALLOC,
    RPC_ERR_UNIMPL_CALL,
    RPC_ERR_BACKEND,
    RPC_ERR_COUNT
} RPCError;

/* Use RPCBuffer or RPCString to transfer variable size buffers. */
typedef struct {
    uint16_t size;
    uint8_t *data;
} RPCBuffer;

/* In contrast to `RPCBuffer`, front-end appends zero byte to `data`.
 * The byte is not accounted in `length`. */
typedef struct {
    uint16_t length;
    uint8_t *data;
} RPCString;

typedef void * rpc_ptr_t;

typedef rpc_ptr_t (*rpc_alloc_t)(size_t);
typedef void (*rpc_free_t)(rpc_ptr_t);

/* An implementation can force own heap API. <malloc.h> is default. */
extern rpc_alloc_t rpc_alloc;
extern rpc_free_t rpc_free;

/* RPCServer uses rpc_read_t and rpc_write_t functions to communicate with
 * other end through rpc_connection_t. An implementation must establish it
 * by self providing the functions. RPCServer uses rpc_connection_t value as
 * an opaque pointer. Example: stdio-connection.h */
typedef rpc_ptr_t rpc_connection_t;

typedef size_t (*rpc_read_t)(rpc_connection_t, rpc_ptr_t, size_t);
typedef size_t (*rpc_write_t)(rpc_connection_t, rpc_ptr_t, size_t);

typedef struct RPCServer RPCServer;

/* ctx is an opaque pointer the RPCServer passes to implementation handlers
 * of commands. RPCServer treats it as an opaque pointer-length integer. It
 * can be any, e.g. NULL if not required. */

RPCServer* rpc_server_new(rpc_connection_t, rpc_read_t, rpc_write_t,
        rpc_ptr_t ctx, RPCError*);
void rpc_server_delete(RPCServer*);
RPCError rpc_server_poll(RPCServer*);

/* internal */

typedef void *RPCBackEnd;

RPCBackEnd rpc_backend_new(RPCError*);
void rpc_backend_free(RPCBackEnd, RPCError*);
RPCError rpc_backend_handle_message(RPCBackEnd, rpc_ptr_t ctx,
        rpc_ptr_t msg, uint32_t msg_size,
        uint8_t** response, uint32_t* response_size);
RPCError rpc_backend_alloc_response(RPCBackEnd, uint32_t response_size,
        uint8_t** response);

#endif /* QDT_RPC_RPC_H */
