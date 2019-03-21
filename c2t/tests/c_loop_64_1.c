/* Control flow instruction */

#include <stdint.h>

void main(void)
{
    volatile int64_t c, i;

    for(i = 0; i < 0x17; i++) {
        c = i;
        c = 0; //$ch.c, ch.i, chc.c, chc.i
    }

    return;    //$bre
}
