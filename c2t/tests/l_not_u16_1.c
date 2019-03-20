//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint16_t a = 0x7c36, c;

    c = ~a;
    c = 0;     //$ch.c

    return;    //$bre
}
