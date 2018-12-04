//Control flow instruction

#include <stdint.h>

void main(void)
{
    volatile int32_t a = 0xc907830f, b = 0xc27c9d8b, c;

    if (a == b) {
        c = 1;  //$ch.c
    } else {
        c = -1; //$ch.c
    }

    return;     //$bre
}
