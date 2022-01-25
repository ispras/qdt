#ifndef RPC_ARRAY_H
#define RPC_ARRAY_H

#include <malloc.h>

#define ARRAY_DECL(TYPE, NAME) \
    TYPE *NAME; \
    int NAME##_allocated; \
    int NAME##_used

#define ARRAY_ALLOC(NAME) do { \
    NAME = malloc(sizeof(typeof(*NAME))); \
    NAME##_allocated = 1; \
    NAME##_used = 0; \
} while ((0))

#define ARRAY_ALLOC_EL(NAME, EL_PTR) do { \
    if (NAME##_used == NAME##_allocated) { \
        NAME##_allocated <<= 1; \
        NAME = realloc(NAME, sizeof(typeof(*NAME)) * NAME##_allocated); \
    } \
    EL_PTR = &NAME[NAME##_used]; \
    NAME##_used++; \
} while ((0))

#define ARRAY_INDEX(NAME, EL_PTR) ((EL_PTR) - (NAME))

#define ARRAY_FREE(NAME) do { \
    free(NAME); \
    NAME##_allocated = 0; \
    NAME##_used = 0; \
} while ((0))

#endif /* RPC_ARRAY_H */
