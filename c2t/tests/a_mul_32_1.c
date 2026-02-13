/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int32_t a = 0xd45392a5, b = 0x7ca32, c;

    c = a * b;
    c = 0;     //$ch.c

    return;    //$bre
}

