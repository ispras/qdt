/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile int32_t a = 0xd2835f1, b = 0xa, c;

    c = a << b;
    c = 0;     //$ch.c

    return;    //$bre
}
