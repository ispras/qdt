/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile uint8_t a = 0xef, b = 0x4, c;

    c = a << b;
    c = 0;     //$ch.c

    return;    //$bre
}
