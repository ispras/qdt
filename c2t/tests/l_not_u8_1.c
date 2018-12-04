//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint8_t a = 0x7e, c;

    c = ~a;
    c = 0;     //$ch.c

    return;    //$bre
}
