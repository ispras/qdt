//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int64_t a = 0x21f070e5e2b74f5f, b = 0xce5f14d8a90abdb6, c;

    c = a ^ b;
    c = 0;     //$ch.c

    return;    //$bre
}
