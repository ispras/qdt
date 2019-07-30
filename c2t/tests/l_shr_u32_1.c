/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile uint32_t a = 0x10f17dcfb, b = 0x11, c;

    c = a >> b;
    c = 0;     //$ch.c

    return;    //$bre
}
