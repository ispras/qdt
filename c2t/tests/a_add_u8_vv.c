/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile uint8_t a = 0x80, b = 0x1f, c;

    c = a + b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
