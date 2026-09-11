/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int8_t a = 0xd6, b = 0x6f, c;

    c = a ^ b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
