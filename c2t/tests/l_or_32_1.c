//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int32_t a = 0xa37d1cd9, b = 0xcbee3843, c;

    c = a | b;
    c = 0;     //$ch.c

    return;    //$bre
}
