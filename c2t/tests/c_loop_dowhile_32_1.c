/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile int32_t c;
    int32_t i = 10;

    do {
        c = i;
        FLUSH_PIPELINE;
        c = 0; //$ch.c, chc.c
    } while (--i >= 0);

    return;    //$bre
}
