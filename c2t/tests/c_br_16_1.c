//Control flow instruction

#include <stdint.h>

void main(void)
{
    volatile int16_t a = 0xdef6, b = 0xd42f, c;

    if (a == b) {
        c = 1;  //$ch.c
    } else {
        c = -1; //$ch.c
    }

    return;     //$bre
}
