/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int64_t a = 0xff56ecd081652, b = 0x21, c;

    c = a >> b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
