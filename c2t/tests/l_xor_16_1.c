//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int16_t a = 0x8c16, b = 0x44ad, c;

    c = a ^ b;
    c = 0;     //$ch.c

    return;    //$bre
}
