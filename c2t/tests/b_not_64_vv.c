/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int64_t a = 0x1df0e120de3af156, c;

    c = ~a;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
