/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint16_t a = 0xf98b, b = 0xa63a, c;

    c = a | b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
