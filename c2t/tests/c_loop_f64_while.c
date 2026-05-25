#include "common.h"

void main(void)
{
    volatile double i = 0.0;
    register double c;
    c = 10.0;
    while ((c -= 1.0) > 1.0e-300) {
        FLUSH_PIPELINE;

        i++; //$ch.i

        FLUSH_PIPELINE;
    }

    FLUSH_PIPELINE;

    return; //$bre
}
