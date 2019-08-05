/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile int16_t a = 0x901f, b = 0x5, c;

    c = a >> b;
    c = 0;     //$ch.c

    return;    //$bre
}
