//Control flow instruction

#include <stdint.h>

void main(void)
{
    volatile uint8_t a = 0x5d, b = 0xf9, c;

    if (a == b) {
        c = 1;  //$ch.c
    } else {
        c = -1; //$ch.c
    }

    return;     //$bre
}
