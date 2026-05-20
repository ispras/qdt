/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile double a;
    volatile int32_t b = -2345324;

    a = b;

    FLUSH_PIPELINE;

    a = 0;     //$ch.a

    FLUSH_PIPELINE;

    return;    //$bre
}
