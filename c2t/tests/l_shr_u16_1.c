/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile uint16_t a = 0xc76d, b = 0x8, c;

    c = a >> b;
    c = 0;     //$ch.c

    return;    //$bre
}
