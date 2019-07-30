/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile int64_t a = 0x98ab43c8df, b = 0x1f, c;

    c = a << b;
    c = 0;     //$ch.c

    return;    //$bre
}
