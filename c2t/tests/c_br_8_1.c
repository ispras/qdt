//Control flow instruction

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0x2f, b = 0xed, c;

    if (a == b) {
        c = 1;  //$ch.c
    } else {
        c = -1; //$ch.c
    }

    return;     //$bre
}
