/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int32_t a = 0xf1da78b2, b = 0xa87d1, c;

    c = a / b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}

