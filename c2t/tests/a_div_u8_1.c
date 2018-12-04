//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint8_t a = 0x7c, b = 0x3, c;

    c = a / b;
    c = 0;     //$ch.c

    return;    //$bre
}
