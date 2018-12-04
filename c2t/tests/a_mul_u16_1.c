//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint16_t a = 0xc01, b = 0x12, c;

    c = a * b;
    c = 0;     //$ch.c

    return;    //$bre
}
