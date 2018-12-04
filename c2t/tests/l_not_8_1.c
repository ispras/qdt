//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0xb5, c;

    c = ~a;
    c = 0;     //$ch.c

    return;    //$bre
}
