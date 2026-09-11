/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile uint32_t a = 0x192ce100, b = 0x4b4da436, c = 0;

    if (a <= b) {
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
