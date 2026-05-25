/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint32_t a = 0x18d10163, c;

    c = ~a;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
