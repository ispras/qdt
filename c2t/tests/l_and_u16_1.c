/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint16_t a = 0x641e, b = 0x9914, c;

    c = a & b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
