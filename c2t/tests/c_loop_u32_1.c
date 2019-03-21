/* Control flow instruction */

#include <stdint.h>

void main(void)
{
    volatile uint32_t c, i;

    for(i = 0; i < 0xa; i++) {
        c = i;
        c = 0; //$ch.c, ch.i, chc.c, chc.i
    }

    return;    //$bre
}
