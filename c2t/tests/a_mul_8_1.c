//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0x86, b = 0xf2, c;

    c = a * b;
    c = 0;     //$ch.c

    return;    //$bre
}
