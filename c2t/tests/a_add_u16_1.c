//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint16_t a = 0x18c, b = 0x3f4, c;

    c = a + b;
    c = 0;     //$ch.c

    return;    //$bre
}
