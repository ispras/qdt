/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0xb4, b = 0x6, c;

    c = a >> b;
    c = 0;     //$ch.c

    return;    //$bre
}
