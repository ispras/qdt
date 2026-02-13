/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint8_t a = 0xff, b = 0x5, c;

    c = a >> b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
