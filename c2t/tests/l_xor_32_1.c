//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int32_t a = 0x5a0b36f7, b = 0x7a20bc62, c;

    c = a ^ b;
    c = 0;     //$ch.c

    return;    //$bre
}
