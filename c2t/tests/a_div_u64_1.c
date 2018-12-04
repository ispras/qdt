//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint64_t a = 0x18f5d3e6287ab59c, b = 0x89dacb2, c;

    c = a / b;
    c = 0;     //$ch.c

    return;    //$bre
}
