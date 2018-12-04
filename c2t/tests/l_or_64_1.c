//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int64_t a = 0xc1de171ed89aaeaa, b = 0x39380fd3248dd40f, c;

    c = a | b;
    c = 0;     //$ch.c

    return;    //$bre
}
