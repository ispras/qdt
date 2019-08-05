/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile int32_t a = 0xf1d8375, b = 0x16, c;

    c = a >> b;
    c = 0;     //$ch.c

    return;    //$bre
}
