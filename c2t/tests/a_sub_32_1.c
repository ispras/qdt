//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int32_t a = 0xf8dba351, b = 0x800236ab, c;

    c = a - b;
    c = 0;     //$ch.c

    return;    //$bre
}
