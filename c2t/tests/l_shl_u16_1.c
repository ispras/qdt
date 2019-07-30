/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile uint16_t a = 0xf7ac, b = 0x9, c;

    c = a << b;
    c = 0;     //$ch.c

    return;    //$bre
}
