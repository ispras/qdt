/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile double c, i;

    for(i = 0.0; i < 23.0; i+=1.0) {
        c = i;

        FLUSH_PIPELINE;

        c = 0; //$ch.c, ch.i, chc.c, chc.i

        FLUSH_PIPELINE;
    }

    FLUSH_PIPELINE;

    return;    //$bre
}
