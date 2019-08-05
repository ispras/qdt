/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile uint8_t a = 0xff, b = 0x5, c;

    c = a >> b;
    c = 0;     //$ch.c

    return;    //$bre
}
