//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0xcb, b = 0xe7, c;

    c = a | b;
    c = 0;     //$ch.c

    return;    //$bre
}
