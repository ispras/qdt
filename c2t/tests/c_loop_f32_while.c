#include "common.h"

void main(void)
{
    volatile float i = 0.0;
    register float c;
    c = 10.0;
    while ((c -= 1.0) > 1.0e-100) {
        FLUSH_PIPELINE;

        i++; //$ch.i

        FLUSH_PIPELINE;
    }

    FLUSH_PIPELINE;

    return; //$bre
}
