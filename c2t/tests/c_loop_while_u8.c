#include <stdint.h>

void main(void)
{
    volatile uint8_t c, i;
    c = 10;
    while (--c) {
        i++; //$ch.i ch.c
    }
    return; //$bre
}
