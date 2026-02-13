/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile uint8_t c, i;

    for(i = 0; i < 0x7; i++) {
        c = i;
        FLUSH_PIPELINE;
        c = 0; //$ch.c, ch.i, chc.c, chc.i
    }

    return;    //$bre
}
