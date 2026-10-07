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

        FLUSH_PIPELINE;
    } while (--i >= 0);

    FLUSH_PIPELINE;

    return;    //$bre
}
