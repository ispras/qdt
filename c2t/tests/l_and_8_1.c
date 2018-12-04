//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0x9a, b = 0x44, c;

    c = a & b;
    c = 0;     //$ch.c

    return;    //$bre
}
