/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile uint64_t a = 0x18f5d3e6287ab59c, b = 0x89dacb2, c;

    c = a * b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
