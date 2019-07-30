/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile uint32_t a = 0x9ffb17dc, b = 0xc, c;

    c = a << b;
    c = 0;     //$ch.c

    return;    //$bre
}
