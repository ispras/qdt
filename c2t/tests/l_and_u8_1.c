//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint8_t a = 0xe9, b = 0xd5, c;

    c = a & b;
    c = 0;     //$ch.c

    return;    //$bre
}
