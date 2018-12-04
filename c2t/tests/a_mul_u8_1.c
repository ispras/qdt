//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint8_t a = 0x17, b = 0x2d, c;

    c = a * b;
    c = 0;     //$ch.c

    return;    //$bre
}
