//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint16_t a = 0xf98b, b = 0xa63a, c;

    c = a | b;
    c = 0;     //$ch.c

    return;    //$bre
}
