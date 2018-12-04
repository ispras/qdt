//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint32_t a = 0x66b64348, b = 0xced6e31f, c;

    c = a & b;
    c = 0;     //$ch.c

    return;    //$bre
}
