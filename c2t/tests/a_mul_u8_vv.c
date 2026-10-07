/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile uint8_t a = 0x17, b = 0x2d, c;

    c = a * b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
