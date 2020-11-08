/* Arithmetic instruction */

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0x4e, *b, c;
    b = &a;

    c = a + *b;
    c = 0;     //$ch.c

    return;    //$bre
}
