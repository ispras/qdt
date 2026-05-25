/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int16_t a = 0x659e, b = 0x3139, c;

    c = a & b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
