//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint64_t a = 0x8439d966de589b65, b = 0x358351e361863bbc, c;

    c = a ^ b;
    c = 0;     //$ch.c

    return;    //$bre
}
