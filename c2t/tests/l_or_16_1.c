//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int16_t a = 0xd8cd, b = 0x4e88, c;

    c = a | b;
    c = 0;     //$ch.c

    return;    //$bre
}
