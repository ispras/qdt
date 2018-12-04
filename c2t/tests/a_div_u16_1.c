//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint16_t a = 0x1f3e, b = 0xdca, c;

    c = a / b;
    c = 0;     //$ch.c

    return;    //$bre
}
