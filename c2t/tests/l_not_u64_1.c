//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile uint64_t a = 0xbd48c93046c566d5, c;

    c = ~a;
    c = 0;     //$ch.c

    return;    //$bre
}
