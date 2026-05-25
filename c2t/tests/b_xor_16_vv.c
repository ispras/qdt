/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int16_t a = 0x8c16, b = 0x44ad, c;

    c = a ^ b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
