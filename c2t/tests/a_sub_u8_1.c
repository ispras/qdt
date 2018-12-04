//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint8_t a = 0x7e, b = 0x19, c;

    c = a - b;
    c = 0;     //$ch.c

    return;    //$bre
}
