//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int16_t a = 0xf7e1, b = 0x8a0, c;

    c = a / b;
    c = 0;     //$ch.c

    return;    //$bre
}
