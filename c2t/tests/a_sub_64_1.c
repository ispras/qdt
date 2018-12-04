//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int64_t a = 0x9e09236f2341abcd, b = 0xff876da4355b3c93, c;

    c = a - b;
    c = 0;     //$ch.c

    return;    //$bre
}
