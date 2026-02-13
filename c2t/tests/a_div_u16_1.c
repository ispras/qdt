/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile uint16_t a = 0x1f3e, b = 0xdca, c;

    c = a / b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
