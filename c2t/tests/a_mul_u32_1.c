//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint32_t a = 0x67fc6a51, b = 0x97a1c2, c;

    c = a * b;
    c = 0;     //$ch.c

    return;    //$bre
}
