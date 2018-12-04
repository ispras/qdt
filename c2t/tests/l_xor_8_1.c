//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0xd6, b = 0x6f, c;

    c = a ^ b;
    c = 0;     //$ch.c

    return;    //$bre
}
