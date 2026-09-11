/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile uint16_t a = 0xc01, b = 0x12, c;

    c = a * b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
