//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint32_t a = 0x251b325e, b = 0xb01cce3, c;

    c = a + b;
    c = 0;     //$ch.c

    return;    //$bre
}
