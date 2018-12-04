//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int32_t a = 0xf1da78b2, b = 0xa87d1, c;

    c = a / b;
    c = 0;     //$ch.c

    return;    //$bre
}

