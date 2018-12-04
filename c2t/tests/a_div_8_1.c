//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0xf6, b = 0x19, c;

    c = a / b;
    c = 0;     //$ch.c

    return;    //$bre
}
