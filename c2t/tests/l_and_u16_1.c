//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint16_t a = 0x641e, b = 0x9914, c;

    c = a & b;
    c = 0;     //$ch.c

    return;    //$bre
}
