/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int32_t a = 0xf8dba351, b = 0x800236ab, c;

    c = a - b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
