//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int32_t a = 0xb3837873, c;

    c = ~a;
    c = 0;     //$ch.c

    return;    //$bre
}
