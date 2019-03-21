//Control flow instruction

#include <stdint.h>

void main(void)
{
    volatile uint16_t c, i;

    for(i = 0; i < 0x11; i++) {
        c = i;
        c = 0; //$ch.c, ch.i, chc.c, chc.i
    }

    return;    //$bre
}
