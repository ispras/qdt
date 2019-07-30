/* Logical instruction */

#include <stdint.h>

void main(void)
{
    volatile int64_t a = 0xff56ecd081652, b = 0x21, c;

    c = a >> b;
    c = 0;     //$ch.c

    return;    //$bre
}
