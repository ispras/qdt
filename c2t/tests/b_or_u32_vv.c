/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint32_t a = 0x52d3a088, b = 0x564b256d, c;

    c = a | b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
