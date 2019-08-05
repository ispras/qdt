/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0x82, b = 0x2, c;

    c = a << b;
    c = 0;     //$ch.c

    return;    //$bre
}
