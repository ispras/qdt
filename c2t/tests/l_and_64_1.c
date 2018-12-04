//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int64_t a = 0x60764141227e76f4, b = 0xfdf97a16478efb89, c;

    c = a & b;
    c = 0;     //$ch.c

    return;    //$bre
}
