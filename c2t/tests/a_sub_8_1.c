//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0xe3, b = 0xb9, c;

    c = a - b;
    c = 0;     //$ch.c

    return;    //$bre
}
