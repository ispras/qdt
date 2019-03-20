//Logical instruction

#include <stdint.h>

void main(void)
{
    volatile int64_t a = 0x1df0e120de3af156, c;

    c = ~a;
    c = 0;     //$ch.c

    return;    //$bre
}
