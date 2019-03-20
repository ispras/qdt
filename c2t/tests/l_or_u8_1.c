//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint8_t a = 0x79, b = 0xe0, c;

    c = a | b;
    c = 0;     //$ch.c

    return;    //$bre
}
