/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int64_t a = 0x98ab43c8df, b = 0x1f, c;

    c = a << b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
