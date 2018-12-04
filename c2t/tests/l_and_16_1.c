//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int16_t a = 0x659e, b = 0x3139, c;

    c = a & b;
    c = 0;     //$ch.c

    return;    //$bre
}
