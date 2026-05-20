/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int8_t a = 0x86, b = 0xf2, c;

    c = a * b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
