/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int8_t a = 0x82, b = 0x2, c;

    c = a << b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
