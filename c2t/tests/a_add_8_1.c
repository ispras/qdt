//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0x4e, b = 0x8d, c;

    c = a + b;
    c = 0;     //$ch.c

    return;    //$bre
}
