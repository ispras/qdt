//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint64_t a = 0xd365271b20d766f3, b = 0xd09c17badfe744a9, c;

    c = a & b;
    c = 0;     //$ch.c

    return;    //$bre
}
