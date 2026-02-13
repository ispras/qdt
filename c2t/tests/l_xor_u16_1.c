/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint16_t a = 0x1515, b = 0xd7d4, c;

    c = a ^ b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
