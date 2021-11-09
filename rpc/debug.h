#ifndef QDT_RPC_DEBUG_H
#define QDT_RPC_DEBUG_H

#ifndef RPC_DEBUG
#define RPC_DEBUG 0
#endif

#if RPC_DEBUG
#include <stdio.h>
#define LOG(FMT, ...) fprintf(stderr, "RPC: " FMT "\n", ##__VA_ARGS__)
#else
#define LOG(FMT, ...)
#endif

#endif /* QDT_RPC_DEBUG_H */
