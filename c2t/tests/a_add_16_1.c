//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int16_t a = 0xe19a, b = 0xd6ba, c;

    c = a + b;
    c = 0;     //$ch.c

    return;    //$bre
}
