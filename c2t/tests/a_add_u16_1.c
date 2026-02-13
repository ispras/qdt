/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile uint16_t a = 0x18c, b = 0x3f4, c;

    c = a + b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
