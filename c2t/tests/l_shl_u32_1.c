/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint32_t a = 0x9ffb17dc, b = 0xc, c;

    c = a << b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
