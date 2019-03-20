//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint64_t a = 0x5fd2cb36a8e963f4, b = 0x1440fdac235d964b, c;

    c = a - b;
    c = 0;     //$ch.c

    return;    //$bre
}
