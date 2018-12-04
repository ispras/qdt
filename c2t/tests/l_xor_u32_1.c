//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint32_t a = 0xab09f1d2, b = 0xd9dfd291, c;

    c = a ^ b;
    c = 0;     //$ch.c

    return;    //$bre
}
