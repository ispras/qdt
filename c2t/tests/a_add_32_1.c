//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int32_t a = 0xd32a9455, b = 0xa369974e, c;

    c = a + b;
    c = 0;     //$ch.c

    return;    //$bre
}
