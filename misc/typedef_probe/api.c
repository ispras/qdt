#include "api.h"
#include <malloc.h>
#include <stdio.h>

typedef struct {
    int field;
} HandleImpl;

Handle api_new(void)
{
    return malloc(sizeof(HandleImpl));
}

void api_use(Handle h)
{
    printf("Hello from API\n");
}

void api_delete(Handle h)
{
    free(h);
}
