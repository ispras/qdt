/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int16_t a = 0xd8cd, b = 0x4e88, c;

    c = a | b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
