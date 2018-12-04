//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint16_t a = 0x1515, b = 0xd7d4, c;

    c = a ^ b;
    c = 0;     //$ch.c

    return;    //$bre
}
