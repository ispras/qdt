/* Control flow instruction */

#include <stdint.h>

int8_t func(int8_t a) {
    return a;
}

void main(void)
{
    volatile int8_t a = 0x3b, c;

    c = func(a);
    c = 0;     //$ch.c

    return;    //$bre
}
