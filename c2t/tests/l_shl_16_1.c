/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile int16_t a = 0x8617, b = 0x7, c;

    c = a << b;
    c = 0;     //$ch.c

    return;    //$bre
}
