//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint64_t a = 0xf3c4165f4edccfed, b = 0x1a0088a5828f8b9d, c;

    c = a | b;
    c = 0;     //$ch.c

    return;    //$bre
}
