/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile int8_t a = 0x2f, b = 0xed, c = 0;

    if (a < b) {
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
