/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile int16_t a = 0xdef6, b = 0xd42f, c = 0;

    if (a == b) {
        FLUSH_PIPELINE;

        c = 1;  //$br

        FLUSH_PIPELINE;
    } else {
        FLUSH_PIPELINE;

        c = -1; //$br

        FLUSH_PIPELINE;
    }

    FLUSH_PIPELINE;

    return;     //$bre
}
