/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint64_t a = 0x637d1bf63702d5, b = 0x2c, c;

    c = a >> b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
