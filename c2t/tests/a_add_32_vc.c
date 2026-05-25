/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int32_t a = 0xd32a9455, c;

    c = a + 42;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
