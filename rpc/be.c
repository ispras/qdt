#include "rpc.h"
#include "debug.h"

typedef struct {
    rpc_ptr_t response;
    uint32_t response_size;
} RPCBackEndState;

RPCBackEnd rpc_backend_new(RPCError *err)
{
    RPCBackEndState *be = rpc_alloc(sizeof(RPCBackEndState));
    if (be == NULL) {
        if (err != NULL) {
            *err = RPC_ERR_ALLOC;
        }
        return NULL;
    }
    /* Preallocate cache for response */
    be->response_size = 1 << 10;
    be->response = rpc_alloc(be->response_size);
    if (be->response == NULL) {
        rpc_free(be);
        if (err != NULL) {
            *err = RPC_ERR_ALLOC;
        }
        return NULL;
    }
    return (RPCBackEnd)be;
}

void rpc_backend_free(RPCBackEnd rpcbe, RPCError *err)
{
    RPCBackEndState *be = (RPCBackEndState *)rpcbe;
    rpc_free(be->response);
    rpc_free(be);
}

RPCError rpc_backend_alloc_response(RPCBackEnd rpcbe, uint32_t response_size,
        uint8_t** response)
{
    LOG("allocating response %d", response_size);

    RPCBackEndState *be = (RPCBackEndState *)rpcbe;
    if (response_size <= be->response_size) {
        LOG("response reused");

        if (response != NULL) {
            *response = be->response;
        }
    } else {
        uint8_t *new_cache = rpc_alloc(response_size);
        if (new_cache == NULL) {
            LOG("response allocation error");
            return RPC_ERR_ALLOC;
        } else {
            LOG("response allocated");
        }
        rpc_free(be->response);
        be->response = new_cache;
        be->response_size = response_size;

        if (response != NULL) {
            *response = new_cache;
        }
    }
    return RPC_ERR_NO;
}
