/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile uint16_t a = 0x51c8, b = 0x32e7, c;

    c = a - b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
