/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int16_t a = 0xdd91, b = 0xfe43, c;

    c = a - b;
    c = 0;     //$ch.c

    return;    //$bre
}
