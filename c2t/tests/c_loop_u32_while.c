#include "common.h"

void main(void)
{
    volatile uint32_t i = 0;
    register uint32_t c;
    c = 10;
    while (c--) {
        FLUSH_PIPELINE;

        i++; //$ch.i

        FLUSH_PIPELINE;
    }

    FLUSH_PIPELINE;

    return; //$bre
}
