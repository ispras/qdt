//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile int64_t a = 0x8040ca5b9120ef1c, b = 0xf6ff291375f670fd, c;

    c = a + b;
    c = 0;     //$ch.c

    return;    //$bre
}
